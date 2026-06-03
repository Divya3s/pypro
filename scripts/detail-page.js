const params = new URLSearchParams(window.location.search);
const reportId = params.get('id');
const form = document.getElementById('detailForm');
const deleteButton = document.getElementById('deleteButton');
const statusMessage = document.getElementById('statusMessage');
const commentsList = document.getElementById('commentsList');
const commentForm = document.getElementById('commentForm');
const titleBadge = document.getElementById('titleBadge');

const fieldIds = [
  'report_type', 'priority', 'status', 'title', 'reporter_name', 'reporter_email',
  'product_area', 'version_build', 'environment_name', 'severity',
  'requested_resolution_date', 'description', 'steps_to_reproduce',
  'acceptance_criteria', 'actual_result', 'business_impact', 'assignee', 'labels'
];

const escapeHtml = (value) => String(value ?? '')
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#039;');

const setMessage = (message, variant = 'info') => {
  statusMessage.className = `alert alert-${variant}`;
  statusMessage.textContent = message;
};

const getValue = (id) => document.getElementById(id).value.trim();

const formPayload = () => Object.fromEntries(fieldIds.map((id) => [id, getValue(id)]));

const populateForm = (report) => {
  fieldIds.forEach((id) => {
    const field = document.getElementById(id);
    if (field) {
      field.value = report[id] || '';
    }
  });
  titleBadge.textContent = `Report #${report.id}`;
};

const renderComments = (comments = []) => {
  commentsList.innerHTML = '';
  if (!comments.length) {
    commentsList.innerHTML = '<p class="text-muted mb-0">No comments yet.</p>';
    return;
  }

  comments.forEach((comment) => {
    const item = document.createElement('div');
    item.className = 'border rounded-3 p-3 mb-3 bg-light';
    item.innerHTML = `
      <div class="d-flex justify-content-between gap-3 flex-wrap">
        <strong>${escapeHtml(comment.author_name)}</strong>
        <small class="text-muted">${escapeHtml(comment.created_at)}</small>
      </div>
      <p class="mb-0 mt-2">${escapeHtml(comment.comment_body)}</p>
    `;
    commentsList.appendChild(item);
  });
};

const loadReport = async () => {
  if (!reportId) {
    setMessage('Missing report id in the page URL.', 'danger');
    form.classList.add('d-none');
    return;
  }

  const response = await fetch(`/api/reports/${reportId}`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || 'Unable to load report.');
  }
  populateForm(data.report);
  renderComments(data.report.comments);
  setMessage('Report loaded. Edit fields below, then save changes.', 'success');
};

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!form.checkValidity()) {
    form.classList.add('was-validated');
    return;
  }

  const response = await fetch(`/api/reports/${reportId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(formPayload())
  });
  const data = await response.json();
  if (!response.ok) {
    setMessage(data.error || 'Unable to update report.', 'danger');
    return;
  }
  populateForm(data.report);
  setMessage('Report updated successfully.', 'success');
});

deleteButton.addEventListener('click', async () => {
  if (!confirm('Delete this report and its comments?')) {
    return;
  }

  const response = await fetch(`/api/reports/${reportId}`, { method: 'DELETE' });
  const data = await response.json();
  if (!response.ok) {
    setMessage(data.error || 'Unable to delete report.', 'danger');
    return;
  }
  setMessage('Report deleted. Redirecting to bug list...', 'warning');
  setTimeout(() => { window.location.href = 'bugs.html'; }, 900);
});

commentForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const payload = {
    report_id: Number(reportId),
    author_name: getValue('comment_author') || getValue('reporter_name') || 'Anonymous',
    author_email: getValue('comment_email'),
    comment_body: getValue('comment_body')
  };
  if (!payload.comment_body) {
    document.getElementById('comment_body').focus();
    return;
  }

  const response = await fetch('/api/comments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok) {
    setMessage(data.error || 'Unable to add comment.', 'danger');
    return;
  }
  document.getElementById('comment_body').value = '';
  await loadReport();
  setMessage('Comment added successfully.', 'success');
});

loadReport().catch((error) => {
  setMessage(`${error.message} Start the backend with: python3 app.py`, 'danger');
});
