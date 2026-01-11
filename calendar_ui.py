import calendar
from datetime import date
from flask import Flask, render_template, request, abort

app = Flask(__name__)

entries_by_date = {
    date(2025, 12, 1): ["dummy1", "dummy2"],
    date(2025, 12, 2): ["dummy3"],
}


@app.route("/")
def calendar_view():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)

    if not year or not month:
        today = date.today()
        year, month = today.year, today.month

    cal = calendar.Calendar(firstweekday=6)  # 6: Sunday
    weeks = cal.monthdatescalendar(year, month)

    return render_template(
        "calendar_ui.html",
        year=year,
        month=month,
        weeks=weeks,
        entries_by_date=entries_by_date,
    )


@app.route("/day/<date_str>")
def day_view(date_str: str):
    # str 型から date 型へ
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        abort(404)

    day_entries = entries_by_date.get(target_date, [])

    return render_template(
        "day_view.html", target_date=target_date, day_entries=day_entries
    )


if __name__ == "__main__":
    app.run(debug=True)
