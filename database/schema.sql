-- IssueDesk SQLite schema
-- Loaded automatically by app.py when the backend starts.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS report_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type_name TEXT NOT NULL UNIQUE,
    type_description TEXT
);

CREATE TABLE IF NOT EXISTS priorities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    priority_name TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS statuses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status_name TEXT NOT NULL UNIQUE,
    is_closed INTEGER NOT NULL DEFAULT 0 CHECK (is_closed IN (0, 1))
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type_id INTEGER NOT NULL REFERENCES report_types(id),
    priority_id INTEGER NOT NULL REFERENCES priorities(id),
    status_id INTEGER NOT NULL REFERENCES statuses(id),
    title TEXT NOT NULL,
    reporter_name TEXT NOT NULL,
    reporter_email TEXT NOT NULL,
    product_area TEXT NOT NULL,
    version_build TEXT,
    environment_name TEXT,
    severity TEXT,
    requested_resolution_date TEXT,
    description TEXT NOT NULL,
    steps_to_reproduce TEXT,
    acceptance_criteria TEXT,
    actual_result TEXT,
    business_impact TEXT,
    assignee TEXT,
    labels TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    author_name TEXT NOT NULL,
    author_email TEXT,
    comment_body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    is_internal INTEGER NOT NULL DEFAULT 0 CHECK (is_internal IN (0, 1))
);

CREATE TABLE IF NOT EXISTS report_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_path TEXT,
    file_description TEXT,
    uploaded_by TEXT,
    uploaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    old_status_id INTEGER REFERENCES statuses(id),
    new_status_id INTEGER NOT NULL REFERENCES statuses(id),
    changed_by TEXT NOT NULL,
    change_note TEXT,
    changed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reports_status_id ON reports(status_id);
CREATE INDEX IF NOT EXISTS idx_reports_priority_id ON reports(priority_id);
CREATE INDEX IF NOT EXISTS idx_reports_product_area ON reports(product_area);
CREATE INDEX IF NOT EXISTS idx_report_comments_report_id ON report_comments(report_id);
CREATE INDEX IF NOT EXISTS idx_report_attachments_report_id ON report_attachments(report_id);
CREATE INDEX IF NOT EXISTS idx_report_status_history_report_id ON report_status_history(report_id);

INSERT OR IGNORE INTO report_types (type_name, type_description) VALUES
    ('Bug', 'Unexpected behavior, defect, or regression.'),
    ('Feature Request', 'New product capability or workflow.'),
    ('Improvement', 'Enhancement to an existing capability.'),
    ('Documentation', 'Documentation gap or clarification request.');

INSERT OR IGNORE INTO priorities (priority_name, sort_order) VALUES
    ('Critical', 1),
    ('High', 2),
    ('Medium', 3),
    ('Low', 4);

INSERT OR IGNORE INTO statuses (status_name, is_closed) VALUES
    ('New', 0),
    ('Triaging', 0),
    ('Planned', 0),
    ('In progress', 0),
    ('Resolved', 1);
