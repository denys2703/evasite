const state = {
  vehicles: [],
  statuses: [],
  filters: {
    brand: '',
    status: '',
    location: '',
    year: ''
  }
};

const cardsContainer = document.getElementById('vehicle-cards');
const filtersContainer = document.getElementById('filters');
const catalogView = document.getElementById('catalog-view');
const detailView = document.getElementById('detail-view');
const detailTitle = document.getElementById('detail-title');
const detailTable = document.getElementById('detail-table');
const detailDescription = document.getElementById('detail-description');
const detailStatus = document.getElementById('detail-status');
const backButton = document.getElementById('back-button');

function normalizeStatus(status) {
  return status.toLowerCase().replace(/\s+/g, '-');
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || 'Request failed');
  }
  return data;
}

function uniqueValues(list, key) {
  return [...new Set(list.map((item) => item[key]).filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b)));
}

function createFilter(label, key, options) {
  const wrapper = document.createElement('div');
  wrapper.className = 'filter-group';

  const title = document.createElement('label');
  title.textContent = label;
  title.setAttribute('for', `filter-${key}`);

  const select = document.createElement('select');
  select.id = `filter-${key}`;
  select.innerHTML = `<option value="">All ${label}</option>` + options.map((option) => `<option value="${option}">${option}</option>`).join('');
  select.value = state.filters[key];
  select.addEventListener('change', (event) => {
    state.filters[key] = event.target.value;
    renderCards();
  });

  wrapper.appendChild(title);
  wrapper.appendChild(select);
  return wrapper;
}

function filteredVehicles() {
  return state.vehicles.filter((vehicle) => (
    (!state.filters.brand || vehicle.brand === state.filters.brand)
    && (!state.filters.status || vehicle.status === state.filters.status)
    && (!state.filters.location || vehicle.location === state.filters.location)
    && (!state.filters.year || vehicle.year === state.filters.year)
  ));
}

function renderFilters() {
  filtersContainer.innerHTML = '';
  filtersContainer.appendChild(createFilter('Brand', 'brand', uniqueValues(state.vehicles, 'brand')));
  filtersContainer.appendChild(createFilter('Status', 'status', uniqueValues(state.vehicles, 'status')));
  filtersContainer.appendChild(createFilter('Location', 'location', uniqueValues(state.vehicles, 'location')));
  filtersContainer.appendChild(createFilter('Year', 'year', uniqueValues(state.vehicles, 'year')));
}

function renderCards() {
  cardsContainer.innerHTML = '';
  const rows = filteredVehicles();

  if (rows.length === 0) {
    const empty = document.createElement('p');
    empty.textContent = 'No vehicles match your current filters.';
    cardsContainer.appendChild(empty);
    return;
  }

  rows.forEach((vehicle) => {
    const card = document.createElement('article');
    card.className = 'card';
    card.addEventListener('click', () => {
      window.location.hash = `#vehicle/${vehicle.id}`;
    });

    card.innerHTML = `
      <h2 class="card-label">${vehicle.id} ${vehicle.brand}</h2>
      <p class="card-meta">${vehicle.model} • ${vehicle.year}</p>
      <p class="card-meta">${vehicle.location}</p>
      <span class="badge ${normalizeStatus(vehicle.status)}">${vehicle.status}</span>
    `;

    cardsContainer.appendChild(card);
  });
}

function renderDetail(vehicle) {
  catalogView.classList.add('hidden');
  detailView.classList.remove('hidden');

  detailTitle.textContent = `${vehicle.id} ${vehicle.brand} ${vehicle.model}`;
  detailDescription.textContent = vehicle.description || 'No description provided.';

  detailTable.innerHTML = [
    ['ID', vehicle.id],
    ['Brand', vehicle.brand],
    ['Model', vehicle.model],
    ['Year', vehicle.year],
    ['VIN', vehicle.vin],
    ['Status', vehicle.status],
    ['Location', vehicle.location]
  ].map(([field, value]) => `<tr><th>${field}</th><td>${value || '-'}</td></tr>`).join('');

  detailStatus.innerHTML = state.statuses.map((status) => `<option value="${status}">${status}</option>`).join('');
  detailStatus.value = vehicle.status;
  detailStatus.onchange = async () => {
    await updateStatus(vehicle.id, detailStatus.value);
  };
}

async function updateStatus(id, status) {
  await fetchJson(`/api/vehicles/${encodeURIComponent(id)}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status })
  });

  const target = state.vehicles.find((vehicle) => vehicle.id === id);
  if (target) {
    target.status = status;
  }

  renderCards();
  if (window.location.hash.startsWith('#vehicle/')) {
    renderDetail(target);
  }
}

function renderRoute() {
  const hash = window.location.hash || '#catalog';
  if (!hash.startsWith('#vehicle/')) {
    detailView.classList.add('hidden');
    catalogView.classList.remove('hidden');
    return;
  }

  const id = decodeURIComponent(hash.split('/')[1] || '');
  const vehicle = state.vehicles.find((item) => item.id === id);
  if (!vehicle) {
    window.location.hash = '#catalog';
    return;
  }

  renderDetail(vehicle);
}

async function bootstrap() {
  const [vehiclesData, statusData] = await Promise.all([
    fetchJson('/api/vehicles'),
    fetchJson('/api/statuses')
  ]);

  state.vehicles = vehiclesData.vehicles;
  state.statuses = statusData.statuses;

  renderFilters();
  renderCards();
  renderRoute();
}

window.addEventListener('hashchange', renderRoute);
backButton.addEventListener('click', () => {
  window.location.hash = '#catalog';
});

bootstrap().catch((error) => {
  cardsContainer.textContent = error.message;
});
