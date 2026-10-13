from app import create_app

app = create_app()

with app.test_request_context('/admin'):
    html = app.jinja_env.get_template('admin.html').render(
        kpis={
            'avg_delay': 0,
            'on_time_pct': 0,
            'severe_delays': 0,
            'worst_line': '-',
        },
        reliab=[],
        summary=[],
        risk=[],
        risk_label={'high': 'High', 'medium': 'Moderate', 'low': 'Low'},
        hotspots=[],
        worst_hour={},
        month_names=[],
        monsoon_series={},
        heat_rows=[{'line': 'Line A', 'values': [0, 1, 2, 3]}],
        wettest=[],
    )
    print('ok', 'Line A' in html, 'No hourly delay data available yet' in html)
