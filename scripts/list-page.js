const reportType = document.body.dataset.reportType;
const tableBody = document.getElementById('reportsBody');
const emptyState = document.getElementById('emptyState');
const pageTitle = document.getElementById('pageTitle');
const pageSubtitle = document.getElementById('pageSubtitle');

const typeCopy = {
  Bug: ['Bug reports', 'Review defects, regressions, and broken workflows.'],
  'Feature Request': ['Feature requests', 'Review requested product capabilities and new workflows.'],
  Documentation: ['Documentation reports', 'Review docs gaps, unclear guidance, and content requests.'],
  Improvement: ['Improvement reports', 'Review enhancements to existing product experiences.']
};

const escapeHtml = (value) => String(value ?? '')
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#039;');

const badgeClass = (priority) => ({
  Critical: 'text-bg-danger',
  High: 'text-bg-warning',
  Medium: 'text-bg-primary',
  Low: 'text-bg-secondary'
}[priority] || 'text-bg-light');

const renderReports = (reports) => {
  tableBody.innerHTML = '';
  emptyState.classList.toggle('d-none', reports.length > 0);

  reports.forEach((report) => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td class="fw-semibold">#${report.id}</td>
      <td>
        <div class="fw-semibold">${escapeHtml(report.title)}</div>
        <small class="text-muted">${escapeHtml(report.product_area)}</small>
      </td>
      <td><span class="badge ${badgeClass(report.priority)}">${escapeHtml(report.priority)}</span></td>
      <td>${escapeHtml(report.status)}</td>
      <td>${escapeHtml(report.assignee || 'Unassigned')}</td>
      <td><small>${escapeHtml(report.updated_at || report.created_at)}</small></td>
      <td class="text-end"><a class="btn btn-sm btn-outline-primary" href="detail.html?id=${report.id}">View details</a></td>
    `;
    tableBody.appendChild(row);
  });
};

const loadReports = async () => {
  const [title, subtitle] = typeCopy[reportType] || ['Reports', 'Review submitted reports.'];
  pageTitle.textContent = title;
  pageSubtitle.textContent = subtitle;

  const response = await fetch(`/api/reports?type=${encodeURIComponent(reportType)}`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || 'Unable to load reports.');
  }
  renderReports(data.reports);
};

loadReports().catch((error) => {
  emptyState.classList.remove('d-none');
  emptyState.textContent = `${error.message} Start the backend with: python3 app.py`;
});
