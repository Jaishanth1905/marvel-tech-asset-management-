from flask import abort, redirect, request, url_for
from app import app
@app.before_request
def employee_portal_only():
    # Let CSS, JavaScript, images, and uploaded files load.
    if request.path.startswith("/static/"):
        return None
    # Let uploaded logos, flags, asset images, and ticket attachments load.
    if request.path.startswith("/uploads/"):
        return None
    # When opening port 5002, send users to the employee login page.
    if request.path == "/":
        return redirect(url_for("employee_login"))
    # Allow only employee pages on port 5002.
    if request.path.startswith("/employee"):
        return None
    # Block admin pages such as /tickets and /reports.
    abort(404)
if __name__ == "__main__":
    print("=" * 60)
    print("MARVELTECH EMPLOYEE PORTAL")
    print("=" * 60)
    print("Asset Management Portal:  http://localhost:5001/  (run app.py separately)")
    print("Employee Portal:          http://localhost:5002/")
    print("=" * 60)
    app.run(
        debug=True,
        use_reloader=False,
        host="0.0.0.0",
        port=5002
    )