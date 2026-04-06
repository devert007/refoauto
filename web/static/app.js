/**
 * RefoAuto Web UI — vanilla JS application
 */

const app = {
  state: {
    currentClient: null,
    clients: [],
    settings: {},
    fields: [],
    pipelinePolling: null,
    generatePolling: null,
  },

  // === Model Field Definitions (from pydantic_models.py) ===

  MODEL_FIELDS: {
    categories: [
      { key: 'id', target: 'id', type: 'int', desc: 'Unique category identifier' },
      { key: 'name_i18n', target: 'name_i18n', type: 'i18n', desc: 'Category name {en, ru}' },
      { key: 'sort_order', target: 'sort_order', type: 'int', desc: 'Sort order (lower = first)' },
    ],
    services: [
      { key: 'id', target: 'id', type: 'int', desc: 'Unique service identifier' },
      { key: 'category_id', target: 'category_id', type: 'int', desc: 'FK to ServiceCategory' },
      { key: 'name_i18n', target: 'name_i18n', type: 'i18n', desc: 'Service name {en, ru}' },
      { key: 'description_i18n', target: 'description_i18n', type: 'i18n', desc: 'Description {en, ru}' },
      { key: 'aliases', target: 'aliases', type: 'list[str]', desc: 'Alternative names for AI matching' },
      { key: 'duration_minutes', target: 'duration_minutes', type: 'int', desc: 'Duration in minutes' },
      { key: 'capacity', target: 'capacity', type: 'int', desc: 'Max clients per session (1=individual)' },
      { key: 'price_type', target: 'price_type', type: 'enum', desc: 'fixed / range / unknown', options: ['fixed', 'range', 'unknown'] },
      { key: 'price_min', target: 'price_min', type: 'float', desc: 'Minimum price' },
      { key: 'price_max', target: 'price_max', type: 'float', desc: 'Maximum price' },
      { key: 'price_note_i18n', target: 'price_note_i18n', type: 'i18n', desc: 'Price notes {en, ru}' },
      { key: 'prepaid', target: 'prepaid', type: 'enum', desc: 'Prepayment policy', options: ['forbidden', 'allowed', 'required'] },
      { key: 'booking_mode', target: 'booking_mode', type: 'enum', desc: 'Booking mode', options: ['slots', 'request'] },
      { key: 'branches', target: 'branches', type: 'list[str]', desc: 'Branch names where available' },
      { key: 'is_visible_to_ai', target: 'is_visible_to_ai', type: 'bool', desc: 'AI can see and book this' },
      { key: 'is_archived', target: 'is_archived', type: 'bool', desc: 'Hidden from active listings' },
      { key: 'sort_order', target: 'sort_order', type: 'int', desc: 'Display sort order' },
      { key: 'source', target: 'source', type: 'str', desc: 'Data source: manual / Altegio / etc.' },
      { key: 'external_id', target: 'external_id', type: 'str', desc: 'External ID from EHR system' },
      { key: 'is_group_service', target: 'is_group_service', type: 'bool', desc: 'Group service (capacity > 1)' },
      { key: 'overridden_fields', target: 'overridden_fields', type: 'list[str]', desc: 'Fields manually overridden' },
    ],
    practitioners: [
      { key: 'id', target: 'id', type: 'int', desc: 'Unique practitioner identifier' },
      { key: 'name', target: 'name', type: 'str', desc: 'Full name (e.g. Dr. Anna Zakhozha)' },
      { key: 'name_i18n', target: 'name_i18n', type: 'i18n', desc: 'Name {en, ru}' },
      { key: 'speciality', target: 'speciality', type: 'str', desc: 'Medical speciality' },
      { key: 'sex', target: 'sex', type: 'enum', desc: 'Sex / Gender', options: ['male', 'female'] },
      { key: 'languages', target: 'languages', type: 'list[str]', desc: 'Languages spoken (ENGLISH, RUSSIAN, ...)' },
      { key: 'description_i18n', target: 'description_i18n', type: 'i18n', desc: 'Biography / description {en, ru}' },
      { key: 'years_of_experience', target: 'years_of_experience', type: 'int', desc: 'Years of experience' },
      { key: 'primary_qualifications', target: 'primary_qualifications', type: 'str', desc: 'Degrees, residency, board certs' },
      { key: 'secondary_qualifications', target: 'secondary_qualifications', type: 'str', desc: 'Fellowships, memberships' },
      { key: 'additional_qualifications', target: 'additional_qualifications', type: 'str', desc: 'Additional certs, trainings' },
      { key: 'treat_children', target: 'treat_children', type: 'bool', desc: 'Treats children' },
      { key: 'treat_children_age', target: 'treat_children_age', type: 'str', desc: 'Min age for children (13+, Any age)' },
      { key: 'branches', target: 'branches', type: 'list[str]', desc: 'Clinic branches' },
      { key: 'is_visible_to_ai', target: 'is_visible_to_ai', type: 'bool', desc: 'AI can recommend this doctor' },
      { key: 'is_archived', target: 'is_archived', type: 'bool', desc: 'Archived (hidden)' },
      { key: 'external_id', target: 'external_id', type: 'str', desc: 'External ID from EHR' },
      { key: 'source', target: 'source', type: 'str', desc: 'Data source: manual / google_sheets / Altegio' },
    ],
  },

  // Render a mapping section for any entity type
  _renderMappingFields(containerId, entityType) {
    const container = document.getElementById(containerId);
    const fields = this.MODEL_FIELDS[entityType] || [];
    const savedCols = this.state.settings?.field_mappings?.[entityType]?.columns || {};

    container.innerHTML = '';

    for (const field of fields) {
      const saved = savedCols[field.key] || {};
      const row = document.createElement('div');
      row.className = 'mapping-row';

      let typeTag = `<span class="badge badge-info">${field.type}</span>`;

      row.innerHTML = `
        <div>
          <label>Source: ${field.key} ${typeTag}</label>
          <input type="text" data-entity="${entityType}" data-field="${field.key}" data-prop="source"
                 value="${saved.source || ''}" placeholder="Source column name">
        </div>
        <div>
          <label>Target</label>
          <input type="text" value="${field.target}" readonly>
          <div style="font-size:11px;color:var(--text-muted);margin-top:2px">${field.desc}</div>
        </div>
        <div>
          <label>Rules / Prompt</label>
          <textarea data-entity="${entityType}" data-field="${field.key}" data-prop="rules"
                    placeholder="Parsing/mapping rules...">${saved.rules || ''}</textarea>
        </div>
      `;
      container.appendChild(row);
    }
  },

  // Collect mapping data from rendered fields
  _collectMappingFields(entityType) {
    const columns = {};
    const inputs = document.querySelectorAll(`[data-entity="${entityType}"]`);

    inputs.forEach(input => {
      const field = input.dataset.field;
      const prop = input.dataset.prop;
      if (!columns[field]) columns[field] = {};
      columns[field][prop] = input.value;
    });

    return { columns };
  },

  // === API Layer ===

  async api(method, path, body = null) {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (body && method !== 'GET') {
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(`/api${path}`, opts);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(err.error || res.statusText);
    }
    return res.json();
  },

  // === Init ===

  async init() {
    await this.loadClients();
    this.checkAuth();

    // Auto-select client if only one
    if (this.state.clients.length === 1) {
      document.getElementById('clientSelect').value = this.state.clients[0].name;
      await this.onClientChange(this.state.clients[0].name);
    }
  },

  // === Auth ===

  async checkAuth() {
    try {
      const status = await this.api('GET', '/auth/status');
      const badge = document.getElementById('authBadge');
      if (status.valid) {
        const expDate = new Date(status.expires_at * 1000).toLocaleDateString();
        badge.textContent = `Auth: Valid (until ${expDate})`;
        badge.className = 'auth-badge valid';
      } else {
        badge.textContent = 'Auth: Invalid';
        badge.className = 'auth-badge invalid';
        badge.style.cursor = 'pointer';
        badge.onclick = () => this.refreshAuth();
      }
    } catch (e) {
      const badge = document.getElementById('authBadge');
      badge.textContent = 'Auth: Error';
      badge.className = 'auth-badge invalid';
    }
  },

  async refreshAuth() {
    const badge = document.getElementById('authBadge');
    badge.textContent = 'Auth: Refreshing...';
    try {
      await this.api('POST', '/auth/refresh');
      await this.checkAuth();
    } catch (e) {
      badge.textContent = 'Auth: Failed - ' + e.message;
    }
  },

  // === Clients ===

  async loadClients() {
    const data = await this.api('GET', '/clients');
    this.state.clients = data.clients || [];

    const select = document.getElementById('clientSelect');
    const current = select.value;
    select.innerHTML = '<option value="">-- Select Client --</option>';

    for (const c of this.state.clients) {
      const opt = document.createElement('option');
      opt.value = c.name;
      opt.textContent = `${c.display_name} ${c.enabled ? '' : '(disabled)'}`;
      select.appendChild(opt);
    }

    if (current) select.value = current;
  },

  async onClientChange(name) {
    if (!name) {
      this.state.currentClient = null;
      this._showConfigEmpty();
      return;
    }

    this.state.currentClient = name;

    // Load client details
    const client = await this.api('GET', `/clients/${name}`);
    this._renderConfig(client);

    // Load settings
    await this.loadSettings();

    // Load files
    await this.loadFiles();

    // Load pipeline
    await this.loadPipeline();
  },

  // === Config Tab ===

  _showConfigEmpty() {
    document.getElementById('configNoClient').style.display = 'block';
    document.getElementById('configForm').style.display = 'none';
    document.getElementById('locationsCard').style.display = 'none';
    document.getElementById('configActions').style.display = 'none';
  },

  _renderConfig(client) {
    document.getElementById('configNoClient').style.display = 'none';
    document.getElementById('configForm').style.display = 'block';
    document.getElementById('locationsCard').style.display = 'block';
    document.getElementById('configActions').style.display = 'flex';

    document.getElementById('cfgName').value = client.name || '';
    document.getElementById('cfgDisplayName').value = client.display_name || '';
    document.getElementById('cfgEnabled').checked = client.enabled !== false;

    this._renderLocations(client.locations || []);
  },

  _renderLocations(locations) {
    const container = document.getElementById('locationsList');
    container.innerHTML = '';

    if (locations.length === 0) {
      container.innerHTML = '<div style="color:var(--text-muted);font-size:13px">No locations configured</div>';
      return;
    }

    for (let i = 0; i < locations.length; i++) {
      const loc = locations[i];
      const row = document.createElement('div');
      row.className = 'location-row';
      row.innerHTML = `
        <input type="number" value="${loc.location_id || ''}" placeholder="ID" data-idx="${i}" data-field="location_id">
        <input type="text" value="${loc.name || ''}" placeholder="Location name" data-idx="${i}" data-field="name">
        <input type="text" value="${loc.branch || ''}" placeholder="Branch" data-idx="${i}" data-field="branch">
        <input type="text" value="${loc.description || ''}" placeholder="Description" data-idx="${i}" data-field="description">
        <button class="btn btn-outline btn-sm" onclick="app.removeLocation(${i})">x</button>
      `;
      container.appendChild(row);
    }
  },

  addLocation() {
    const container = document.getElementById('locationsList');
    const idx = container.children.length;
    const row = document.createElement('div');
    row.className = 'location-row';
    row.innerHTML = `
      <input type="number" placeholder="ID" data-idx="${idx}" data-field="location_id">
      <input type="text" placeholder="Location name" data-idx="${idx}" data-field="name">
      <input type="text" placeholder="Branch" data-idx="${idx}" data-field="branch">
      <input type="text" placeholder="Description" data-idx="${idx}" data-field="description">
      <button class="btn btn-outline btn-sm" onclick="app.removeLocation(${idx})">x</button>
    `;
    container.appendChild(row);
  },

  removeLocation(idx) {
    const rows = document.querySelectorAll('#locationsList .location-row');
    if (rows[idx]) rows[idx].remove();
  },

  _collectLocations() {
    const locations = [];
    const rows = document.querySelectorAll('#locationsList .location-row');
    rows.forEach(row => {
      const inputs = row.querySelectorAll('input');
      const loc = {};
      inputs.forEach(input => {
        const field = input.dataset.field;
        if (field) {
          loc[field] = field === 'location_id' ? (parseInt(input.value) || 0) : input.value;
        }
      });
      if (loc.location_id) locations.push(loc);
    });
    return locations;
  },

  async saveConfig() {
    const name = this.state.currentClient;
    if (!name) return;

    const locations = this._collectLocations();
    const branchToLocation = {};
    locations.forEach(loc => {
      if (loc.branch) branchToLocation[loc.branch] = loc.location_id;
    });

    try {
      await this.api('PUT', `/clients/${name}`, {
        display_name: document.getElementById('cfgDisplayName').value,
        enabled: document.getElementById('cfgEnabled').checked,
        locations,
        branch_to_location: branchToLocation,
      });
      alert('Config saved!');
      await this.loadClients();
    } catch (e) {
      alert('Error: ' + e.message);
    }
  },

  async deleteClient() {
    const name = this.state.currentClient;
    if (!name || !confirm(`Delete client "${name}"? This only removes the config entry, not the files.`)) return;

    try {
      await this.api('DELETE', `/clients/${name}`);
      this.state.currentClient = null;
      document.getElementById('clientSelect').value = '';
      this._showConfigEmpty();
      await this.loadClients();
    } catch (e) {
      alert('Error: ' + e.message);
    }
  },

  // === New Client Dialog ===

  showNewClientDialog() {
    const dialog = document.getElementById('newClientDialog');
    dialog.style.display = 'flex';
  },

  hideNewClientDialog() {
    document.getElementById('newClientDialog').style.display = 'none';
  },

  async createClient() {
    const name = document.getElementById('newClientName').value.trim().toLowerCase().replace(/\s+/g, '_');
    const displayName = document.getElementById('newClientDisplayName').value.trim();
    const locationId = parseInt(document.getElementById('newClientLocationId').value) || 0;
    const locationName = document.getElementById('newClientLocationName').value.trim();

    if (!name) { alert('Client name is required'); return; }

    const locations = [];
    if (locationId) {
      locations.push({
        location_id: locationId,
        name: locationName || 'Main',
        branch: '1',
        description: '',
      });
    }

    try {
      await this.api('POST', '/clients', {
        name,
        display_name: displayName || name,
        locations,
        branch_to_location: locations.length ? { '1': locationId } : {},
      });

      this.hideNewClientDialog();
      await this.loadClients();

      document.getElementById('clientSelect').value = name;
      await this.onClientChange(name);
    } catch (e) {
      alert('Error: ' + e.message);
    }
  },

  // === Upload Tab ===

  async loadFiles() {
    const name = this.state.currentClient;
    if (!name) return;

    const data = await this.api('GET', `/clients/${name}/files`);
    const files = data.files || [];

    // File list
    const container = document.getElementById('fileList');
    if (files.length === 0) {
      container.innerHTML = '<div style="color:var(--text-muted);font-size:13px">No files uploaded</div>';
    } else {
      container.innerHTML = files.map(f =>
        `<div style="display:flex;gap:8px;align-items:center;padding:4px 0">
          <span class="badge badge-info">${f.ext}</span>
          <span>${f.name}</span>
          <span style="color:var(--text-muted);font-size:12px">${(f.size / 1024).toFixed(1)} KB</span>
        </div>`
      ).join('');
    }

    // Extract file select
    const select = document.getElementById('extractFileSelect');
    select.innerHTML = '<option value="">-- Select file --</option>';
    files.forEach(f => {
      const opt = document.createElement('option');
      opt.value = f.name;
      opt.textContent = f.name;
      select.appendChild(opt);
    });
  },

  async uploadFiles() {
    const name = this.state.currentClient;
    if (!name) { alert('Select a client first'); return; }

    const fileInput = document.getElementById('fileUpload');
    if (!fileInput.files.length) { alert('Select files to upload'); return; }

    for (const file of fileInput.files) {
      const formData = new FormData();
      formData.append('file', file);

      await fetch(`/api/upload/${name}`, {
        method: 'POST',
        body: formData,
      });
    }

    fileInput.value = '';
    await this.loadFiles();
  },

  async extractFields() {
    const name = this.state.currentClient;
    const filename = document.getElementById('extractFileSelect').value;
    if (!name || !filename) { alert('Select a client and file'); return; }

    try {
      const data = await this.api('POST', `/extract-fields/${name}`, { filename });
      this.state.fields = data.fields || [];
      this._renderFields();
    } catch (e) {
      alert('Error: ' + e.message);
    }
  },

  _renderFields() {
    const container = document.getElementById('fieldsList');
    const showHidden = document.getElementById('showHiddenFields').checked;

    container.innerHTML = '';

    if (this.state.fields.length === 0) {
      container.innerHTML = '<div class="empty-state">No fields extracted yet</div>';
      return;
    }

    // Header
    container.innerHTML = `
      <div class="field-item" style="border-bottom:2px solid var(--border)">
        <div style="font-weight:600;font-size:12px">Field Name</div>
        <div style="font-weight:600;font-size:12px">Sample Data</div>
        <div style="font-weight:600;font-size:12px">Rules / Prompt</div>
        <div></div>
      </div>
    `;

    this.state.fields.forEach((field, idx) => {
      if (field.hidden && !showHidden) return;

      const div = document.createElement('div');
      div.className = `field-item${field.hidden ? ' hidden' : ''}`;
      div.innerHTML = `
        <div class="field-name">${field.name}</div>
        <div class="field-sample">${(field.sample || []).slice(0, 2).join('<br>')}</div>
        <div class="field-prompt">
          <textarea data-idx="${idx}" onchange="app.state.fields[${idx}].prompt = this.value">${field.prompt || ''}</textarea>
        </div>
        <button class="field-close" onclick="app.toggleFieldHidden(${idx})" title="${field.hidden ? 'Show' : 'Hide'}">${field.hidden ? '+' : 'x'}</button>
      `;
      container.appendChild(div);
    });
  },

  toggleFieldHidden(idx) {
    this.state.fields[idx].hidden = !this.state.fields[idx].hidden;
    this._renderFields();
  },

  // === Settings (Entity Tabs) ===

  async loadSettings() {
    const name = this.state.currentClient;
    if (!name) return;

    try {
      const settings = await this.api('GET', `/clients/${name}/settings`);
      this.state.settings = settings;

      // Populate categories (still has dedicated inputs)
      const catMap = settings.field_mappings?.categories || {};
      document.getElementById('catSourceCol').value = catMap.source_column || '';
      document.getElementById('catRules').value = catMap.rules || '';
      document.getElementById('catTranslation').value = catMap.translation || 'en_only';
      document.getElementById('catSortOrder').value = catMap.sort_order || 'appearance';

      // Render all Service fields dynamically
      this._renderMappingFields('serviceMappings', 'services');

      // Render all Practitioner fields dynamically
      this._renderMappingFields('doctorMappings', 'practitioners');

      // Rules
      document.getElementById('commonRules').value = settings.common_rules || '';

      // Preview
      this._updatePreviews();
    } catch (e) {
      console.error('Failed to load settings:', e);
    }
  },

  async saveEntitySettings(entity) {
    const name = this.state.currentClient;
    if (!name) return;

    const settings = this.state.settings;
    if (!settings.field_mappings) settings.field_mappings = {};

    if (entity === 'categories') {
      settings.field_mappings.categories = {
        source_column: document.getElementById('catSourceCol').value,
        rules: document.getElementById('catRules').value,
        translation: document.getElementById('catTranslation').value,
        sort_order: document.getElementById('catSortOrder').value,
      };
    } else if (entity === 'services') {
      settings.field_mappings.services = this._collectMappingFields('services');
    } else if (entity === 'practitioners') {
      settings.field_mappings.practitioners = this._collectMappingFields('practitioners');
    }

    try {
      await this.api('PUT', `/clients/${name}/settings`, settings);
      alert(`${entity} settings saved!`);
    } catch (e) {
      alert('Error: ' + e.message);
    }
  },

  async saveRules() {
    const name = this.state.currentClient;
    if (!name) return;

    const settings = this.state.settings;
    settings.common_rules = document.getElementById('commonRules').value;

    try {
      await this.api('PUT', `/clients/${name}/settings`, settings);
      alert('Rules saved!');
    } catch (e) {
      alert('Error: ' + e.message);
    }
  },

  loadDefaultRules() {
    const defaultRules = `## Data Priority: API-first

API data is the source of truth for structure (ID, names, category_id, prices).
Local CSV data is the source for descriptions and translations not in API.

## Conflict Resolution

- id: always from API
- name_i18n: from API (don't overwrite if API has it)
- category_id: from API
- price_*: from API
- description_i18n: from CSV if API is empty
- duration_minutes: from API if > 0, else from CSV

## Critical Rules

- NEVER create duplicate services
- Match by normalized name, then category_id, then id
- Only UPDATE existing services, do NOT create new ones
- Always run dry-run before execute
- Support ALL configured locations, not just the first one

## Translation

- Translate descriptions to English and Russian where applicable
- Keep original API names unchanged`;

    document.getElementById('commonRules').value = defaultRules;
  },

  _updatePreviews() {
    // Category preview
    const catPreview = document.getElementById('catPreview');
    const catExample = [{
      id: 1,
      name_i18n: { en: 'Category Name', ru: 'Название категории' },
      sort_order: 1,
    }];
    catPreview.textContent = JSON.stringify(catExample, null, 2);

    // Service preview
    const svcPreview = document.getElementById('svcPreview');
    const svcExample = [{
      id: 1,
      category_id: 1,
      name_i18n: { en: 'Service Name', ru: 'Название услуги' },
      description_i18n: { en: '...', ru: '...' },
      duration_minutes: 30,
      price_min: 500.0,
      price_max: 500.0,
      price_note_i18n: { en: '...' },
      branches: ['main'],
    }];
    svcPreview.textContent = JSON.stringify(svcExample, null, 2);
  },

  // === Pipeline Tab ===

  async loadPipeline() {
    const name = this.state.currentClient;
    if (!name) return;

    const settings = this.state.settings || {};
    const steps = settings.pipeline_steps || [];

    const container = document.getElementById('pipelineSteps');
    if (steps.length === 0) {
      container.innerHTML = '<div class="empty-state">No pipeline steps configured</div>';
      return;
    }

    container.innerHTML = '';
    steps.forEach((step, idx) => {
      const div = document.createElement('div');
      div.className = 'step-item';
      div.innerHTML = `
        <label class="step-toggle">
          <input type="checkbox" data-step="${step.name}" ${step.enabled ? 'checked' : ''}>
          <span class="slider"></span>
        </label>
        <span class="step-name">${step.name}</span>
        <span class="step-desc">${step.description || ''}</span>
        <span class="step-args">${(step.args || []).join(' ')}</span>
      `;
      container.appendChild(div);
    });

    // Location checkboxes
    const locContainer = document.getElementById('locationCheckboxes');
    // Keep the "All" checkbox, add per-location
    const existingPerLoc = locContainer.querySelectorAll('.per-loc');
    existingPerLoc.forEach(el => el.remove());

    const client = this.state.clients.find(c => c.name === name);
    if (client && client.locations) {
      client.locations.forEach(loc => {
        const label = document.createElement('label');
        label.className = 'flex items-center gap-8 per-loc';
        label.style.fontSize = '12px';
        label.innerHTML = `
          <input type="checkbox" class="loc-checkbox" value="${loc.location_id}" checked>
          ${loc.name} (${loc.location_id})
        `;
        locContainer.appendChild(label);
      });
    }
  },

  toggleAllLocations(checkbox) {
    document.querySelectorAll('.loc-checkbox').forEach(cb => {
      cb.checked = checkbox.checked;
    });
  },

  async runPipeline(mode) {
    const name = this.state.currentClient;
    if (!name) { alert('Select a client first'); return; }

    let steps;
    if (mode === 'all') {
      steps = (this.state.settings.pipeline_steps || []).map(s => ({
        name: s.name,
        args: s.args || [],
      }));
    } else {
      // Get checked steps
      const checkboxes = document.querySelectorAll('#pipelineSteps input[type="checkbox"]:checked');
      steps = Array.from(checkboxes).map(cb => {
        const stepName = cb.dataset.step;
        const stepConfig = (this.state.settings.pipeline_steps || []).find(s => s.name === stepName);
        return { name: stepName, args: stepConfig?.args || [] };
      });
    }

    if (steps.length === 0) { alert('No steps selected'); return; }

    // Get selected locations
    const allChecked = document.getElementById('locAll').checked;
    let locations = null;
    if (!allChecked) {
      locations = Array.from(document.querySelectorAll('.loc-checkbox:checked')).map(cb => parseInt(cb.value));
    }

    const pipelineMode = document.getElementById('pipelineMode').value;

    try {
      await this.api('POST', `/pipeline/${name}/run`, {
        steps,
        mode: pipelineMode,
        locations,
      });

      document.getElementById('pipelineLog').textContent = 'Pipeline started...\n';

      // Start polling
      if (this.state.pipelinePolling) clearInterval(this.state.pipelinePolling);
      this.state.pipelinePolling = setInterval(() => this.refreshPipelineLog(), 2000);
    } catch (e) {
      alert('Error: ' + e.message);
    }
  },

  async refreshPipelineLog() {
    const name = this.state.currentClient;
    if (!name) return;

    try {
      const status = await this.api('GET', `/pipeline/${name}/status`);
      const logEl = document.getElementById('pipelineLog');
      logEl.textContent = status.output || 'No output yet...';
      logEl.scrollTop = logEl.scrollHeight;

      if (status.status === 'done' || status.status === 'error') {
        if (this.state.pipelinePolling) {
          clearInterval(this.state.pipelinePolling);
          this.state.pipelinePolling = null;
        }
        logEl.textContent += `\n\n--- Pipeline ${status.status.toUpperCase()} ---`;
      }
    } catch (e) {
      console.error('Failed to refresh log:', e);
    }
  },

  // === Generate with Claude ===

  async runGenerate() {
    const name = this.state.currentClient;
    if (!name) { alert('Select a client first'); return; }

    const scope = document.getElementById('generateScope').value;
    const mergeApi = document.getElementById('genMergeApi').checked;
    const doSync = document.getElementById('genSync').checked;

    const options = {};
    if (scope === 'categories') options.categories_only = true;
    if (scope === 'services') options.services_only = true;
    if (scope === 'practitioners') options.practitioners_only = true;
    if (!mergeApi) { options.no_merge = true; options.no_api = true; }
    if (doSync) options.sync = true;

    const logEl = document.getElementById('generateLog');
    logEl.textContent = 'Starting generation with Claude...\n';

    try {
      await this.api('POST', `/generate/${name}`, options);

      // Start polling
      if (this.state.generatePolling) clearInterval(this.state.generatePolling);
      this.state.generatePolling = setInterval(() => this._pollGenerateStatus(), 2000);
    } catch (e) {
      logEl.textContent = 'Error: ' + e.message;
    }
  },

  async _pollGenerateStatus() {
    const name = this.state.currentClient;
    if (!name) return;

    try {
      const status = await this.api('GET', `/generate/${name}/status`);
      const logEl = document.getElementById('generateLog');
      logEl.textContent = status.output || 'Generating...';
      logEl.scrollTop = logEl.scrollHeight;

      if (status.status === 'done' || status.status === 'error') {
        if (this.state.generatePolling) {
          clearInterval(this.state.generatePolling);
          this.state.generatePolling = null;
        }
        logEl.textContent += `\n\n--- Generation ${status.status.toUpperCase()} ---`;
        if (status.finished_at && status.started_at) {
          logEl.textContent += ` (${(status.finished_at - status.started_at).toFixed(1)}s)`;
        }
      }
    } catch (e) {
      console.error('Generate poll error:', e);
    }
  },

  // === Tab Switching ===

  switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));

    document.querySelector(`.tab[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.add('active');
  },
};

// === Init on load ===
document.addEventListener('DOMContentLoaded', () => app.init());

// Show hidden fields toggle
document.addEventListener('change', (e) => {
  if (e.target.id === 'showHiddenFields') {
    app._renderFields();
  }
});
