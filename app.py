"""Dashboard for the Premier League predictor.

Run:  streamlit run app.py
"""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

DATA = Path(__file__).parent / "predictions"

HOME, DRAW, AWAY = "#2a78d6", "#c3c2b7", "#e34948"
INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"
FONT = "system-ui, -apple-system, Segoe UI, sans-serif"
TESTED_ACCURACY = 0.535


def style(chart: alt.Chart) -> alt.Chart:
    return (
        chart.configure(font=FONT, background="transparent")
        .configure_view(stroke=None)
        .configure_axis(labelColor=MUTED, titleColor=MUTED, gridColor=GRID,
                        domainColor="#c3c2b7", tickColor="#c3c2b7", labelFontSize=12, titleFontSize=12)
        .configure_legend(labelColor=INK, titleColor=MUTED, labelFontSize=12, orient="top")
    )


@st.cache_data
def load():
    latest = sorted(DATA.glob("predictions_*.csv"))[-1]
    fixtures = pd.read_csv(latest)
    for col in ("Home win", "Draw", "Away win"):
        fixtures[col] = fixtures[col].str.rstrip("%").astype(float) / 100
    record = pd.read_csv(DATA / "track_record.csv", parse_dates=["Date"])
    table = pd.read_csv(DATA / "table.csv")
    ratings = pd.read_csv(DATA / "elo_history.csv", parse_dates=["Date"])
    return fixtures, record, table, ratings


def next_round(fixtures: pd.DataFrame) -> None:
    fixtures = fixtures.assign(Match=fixtures["Home"] + " v " + fixtures["Away"])
    order = fixtures["Match"].tolist()
    long = fixtures.melt(id_vars=["Match", "Kick-off"], value_vars=["Home win", "Draw", "Away win"],
                         var_name="Result", value_name="Chance")
    long["Label"] = (long["Chance"] * 100).round().astype(int).astype(str) + "%"

    color = alt.Color("Result:N", title=None,
                      scale=alt.Scale(domain=["Home win", "Draw", "Away win"], range=[HOME, DRAW, AWAY]))
    base = alt.Chart(long).encode(
        y=alt.Y("Match:N", sort=order, title=None, axis=alt.Axis(labelColor=INK, labelLimit=220, ticks=False, domain=False)),
        x=alt.X("Chance:Q", stack="normalize", axis=None),
        order=alt.Order("order:Q"),
    ).transform_calculate(order="datum.Result == 'Home win' ? 0 : datum.Result == 'Draw' ? 1 : 2")

    bars = base.mark_bar(height=22, stroke="#fcfcfb", strokeWidth=2).encode(
        color=color,
        tooltip=[alt.Tooltip("Match:N"), alt.Tooltip("Kick-off:N"), alt.Tooltip("Result:N"),
                 alt.Tooltip("Chance:Q", format=".0%")],
    )
    labels = base.mark_text(align="center", fontSize=12).encode(
        x=alt.X("mid:Q", axis=None),
        text=alt.condition("datum.Chance >= 0.12", "Label:N", alt.value("")),
        color=alt.condition("datum.Result == 'Draw'", alt.value(INK), alt.value("#ffffff")),
    ).transform_stack(
        stack="Chance", groupby=["Match"], as_=["start", "end"], sort=[alt.SortField("order")], offset="normalize"
    ).transform_calculate(mid="(datum.start + datum.end) / 2")

    st.altair_chart(style((bars + labels).properties(height=34 * len(fixtures))), width="stretch")

    no_odds = (fixtures["Model"] != "Elo+xG+odds").sum()
    if no_odds:
        st.caption(f"Bookmaker odds aren't out yet for {no_odds} of these matches, so they use the "
                   "backup model (Elo + xG). They'll update once odds are published.")

    shown = fixtures[["Kick-off", "Match", "Pick"]]
    st.dataframe(shown, hide_index=True, width="stretch")


def track_record(record: pd.DataFrame) -> None:
    if record.empty:
        st.write("No predicted matches have been played yet.")
        return
    correct = (record["Correct"] == "yes").sum()
    a, b, c = st.columns(3)
    a.metric("Matches checked", len(record))
    b.metric(f"Correct ({correct} of {len(record)})", f"{correct / len(record):.0%}")
    c.metric("Expected from testing", f"{TESTED_ACCURACY:.1%}")

    weekly = (record.assign(Week=record["Date"].dt.to_period("W").dt.start_time)
              .groupby("Week")["Correct"].apply(lambda s: (s == "yes").mean()).reset_index())
    if len(weekly) > 1:
        bars = alt.Chart(weekly).mark_bar(color=HOME, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=18).encode(
            x=alt.X("Week:T", title=None, axis=alt.Axis(format="%d %b", grid=False)),
            y=alt.Y("Correct:Q", title="Correct", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
            tooltip=[alt.Tooltip("Week:T", format="%d %b %Y"), alt.Tooltip("Correct:Q", format=".0%")],
        )
        target = alt.Chart(pd.DataFrame({"y": [TESTED_ACCURACY]})).mark_rule(
            color=MUTED, strokeDash=[4, 4]).encode(y="y:Q")
        st.altair_chart(style((bars + target).properties(height=220)), width="stretch")
        st.caption("Dashed line: accuracy in the walk-forward test.")

    st.dataframe(record.sort_values("Date", ascending=False).assign(Date=record["Date"].dt.strftime("%d %b")),
                 hide_index=True, width="stretch")


LABEL_SIDES = {
    "right": {"align": "left", "dx": 8},
    "left": {"align": "right", "dx": -8},
    "above": {"align": "center", "dy": -12},
    "below": {"align": "center", "dy": 13},
}


def place_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Put each team name next to its dot where it doesn't cover another dot or label.
    Sizes are rough estimates in data units for a ~620 x 340 px plot."""
    x, y = df["xG for"], df["xG against"]
    px_x = (x.max() - x.min()) / 560
    px_y = (y.max() - y.min()) / 320
    boxes, sides = [], []

    def box(cx, cy, name, side):
        w, h = 6.2 * len(name) * px_x, 12 * px_y
        gap_x, gap_y = 8 * px_x, 12 * px_y
        return {
            "right": (cx + gap_x, cx + gap_x + w, cy - h / 2, cy + h / 2),
            "left": (cx - gap_x - w, cx - gap_x, cy - h / 2, cy + h / 2),
            "above": (cx - w / 2, cx + w / 2, cy - gap_y - h / 2, cy - gap_y + h / 2),
            "below": (cx - w / 2, cx + w / 2, cy + gap_y - h / 2, cy + gap_y + h / 2),
        }[side]

    def overlaps(a, b):
        return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]

    dots = [(cx - 5 * px_x, cx + 5 * px_x, cy - 5 * px_y, cy + 5 * px_y) for cx, cy in zip(x, y)]
    for i, (cx, cy, name) in enumerate(zip(x, y, df["Team"])):
        for side in LABEL_SIDES:
            b = box(cx, cy, name, side)
            inside = x.min() - 20 * px_x <= b[0] and b[1] <= x.max() + 20 * px_x
            clear = not any(overlaps(b, d) for j, d in enumerate(dots) if j != i)
            if inside and clear and not any(overlaps(b, o) for o in boxes):
                break
        boxes.append(b)
        sides.append(side)
    return df.assign(side=sides)


def teams(table: pd.DataFrame, ratings: pd.DataFrame) -> None:
    st.subheader("Strength rating")
    team = st.selectbox("Team", table["Team"], label_visibility="collapsed")
    line = alt.Chart(ratings[ratings["Team"] == team]).mark_line(color=HOME, strokeWidth=2).encode(
        x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %y", grid=False)),
        y=alt.Y("Elo:Q", title="Elo rating", scale=alt.Scale(zero=False)),
        detail="Season:N",
        tooltip=[alt.Tooltip("Date:T", format="%d %b %Y"), alt.Tooltip("Elo:Q", format=".0f")],
    )
    average = alt.Chart(pd.DataFrame({"y": [1500]})).mark_rule(color=MUTED, strokeDash=[4, 4]).encode(y="y:Q")
    st.altair_chart(style((line + average).properties(height=260)), width="stretch")
    st.caption("Since the start of last season. Dashed line: an average Premier League team (1500).")

    st.subheader("Attack and defence")
    xg = place_labels(table.dropna(subset=["xG for", "xG against"]))
    x = alt.X("xG for:Q", title="Chances created (xG per game)", scale=alt.Scale(zero=False, nice=True))
    y = alt.Y("xG against:Q", title="Chances allowed (xG per game)", scale=alt.Scale(zero=False, reverse=True))
    dots = alt.Chart(xg).mark_circle(size=90, color=HOME, opacity=0.9, stroke="#fcfcfb", strokeWidth=2).encode(
        x=x, y=y,
        tooltip=["Team", alt.Tooltip("xG for:Q", format=".2f"), alt.Tooltip("xG against:Q", format=".2f")],
    )
    layers = [dots]
    for side, props in LABEL_SIDES.items():
        layers.append(alt.Chart(xg[xg["side"] == side]).mark_text(fontSize=11, color=INK, **props)
                      .encode(x=x, y=y, text="Team:N"))
    st.altair_chart(style(alt.layer(*layers).properties(height=420)), width="stretch")
    st.caption("Average over each team's last 20 league games. Top right is best: creates a lot, allows little.")

    st.subheader("Table")
    st.dataframe(table[["Pos", "Team", "P", "W", "D", "L", "GD", "Pts", "Elo"]],
                 hide_index=True, width="stretch", height=35 * len(table) + 38)


st.set_page_config(page_title="Premier League predictions", layout="centered")
fixtures, record, table, ratings = load()

st.title("Premier League predictions")
st.caption(f"Results up to {ratings['Date'].max():%d %B %Y}  ·  "
           "Model: Elo ratings, xG and bookmaker odds")

tab_next, tab_record, tab_teams = st.tabs(["Next round", "Track record", "Teams"])
with tab_next:
    next_round(fixtures)
with tab_record:
    track_record(record)
with tab_teams:
    teams(table, ratings)
