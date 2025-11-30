import calendar
from datetime import date
from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/")
def calendar_view():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)

    if not year or not month:
        today = date.today()
        year, month = today.year, today.month

    cal = calendar.Calendar(firstweekday=6) # 6: Sunday
    weeks = cal.monthdatescalendar(year, month)

    entries_by_date = {
        date(2025, 12, 1): ["dummy1", "dummy2"],
        date(2025, 12, 2): ["dummy3"],
    }

    return render_template(
        "calendar_ui.html", 
        year=year,
        month=month,
        weeks=weeks,
        entries_by_date=entries_by_date
    )

if __name__ == "__main__":
    app.run(debug=True)