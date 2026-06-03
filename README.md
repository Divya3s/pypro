# IssueDesk

IssueDesk is a small bug and feature report system built with a Bootstrap frontend, a core Python backend, and SQLite storage.

## Technology stack

- **Frontend:** HTML, Bootstrap, and vanilla JavaScript in `index.html`.
- **Backend:** Core Python standard-library HTTP server in `app.py`.
- **Database:** SQLite database generated at `database/issuedesk.sqlite` from the checked-in schema in `database/schema.sql`.

## Run locally

```bash
python3 app.py
```

Then open <http://127.0.0.1:8000> in a browser. The backend creates/updates the ignored runtime SQLite database automatically, serves the frontend, and exposes JSON endpoints for saving reports and comments.


## Queue and detail pages

- `bugs.html` lists all saved bug reports.
- `features.html` lists all saved feature requests.
- `documentation.html` lists all saved documentation reports.
- `improvements.html` lists all saved improvement reports.
- `detail.html?id=<report_id>` opens the full report detail page with view, update, delete, and comment operations.

## Download all project files

Start the backend and open <http://127.0.0.1:8000/download/issuedesk-files.zip> to download a ZIP archive containing the frontend, backend, README files, SQLite schema, and the locally generated SQLite database. The same link is available from the SQLite backend card in the UI.
