// Placeholder data. Replaced by Supabase queries in step 3.
const weeks = ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8'];
const cases = [310, 322, 305, 340, 368, 381, 381, 412];

new Chart(document.getElementById('trend'), {
  type: 'line',
  data: {
    labels: weeks,
    datasets: [{ label: 'Cases', data: cases, borderColor: '#0072b2',
      backgroundColor: '#0072b2', pointStyle: 'rectRot', pointRadius: 5, tension: 0 }]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    scales: { y: { beginAtZero: true, title: { display: true, text: 'Cases per week' } } },
    plugins: { legend: { display: false } }
  }
});

const tbody = document.querySelector('#trend-table tbody');
weeks.forEach((w, i) => {
  const tr = document.createElement('tr');
  tr.innerHTML = `<td>${w}</td><td>${cases[i]}</td>`;
  tbody.appendChild(tr);
});
