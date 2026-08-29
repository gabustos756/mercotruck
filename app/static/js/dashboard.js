// Theme Manager (Dark / Light Mode)
function initTheme() {
  const savedTheme = localStorage.getItem('mercotruck_theme') || 'light';
  document.documentElement.setAttribute('data-theme', savedTheme);
  updateThemeButtonUI(savedTheme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('mercotruck_theme', next);
  updateThemeButtonUI(next);
}

function updateThemeButtonUI(theme) {
  const btn = document.getElementById('themeToggleBtn');
  if (btn) {
    btn.innerHTML = theme === 'dark' ? '☀️ Modo Claro' : '🌙 Modo Oscuro';
  }
}

function showLoadingOverlay(subText) {
  const overlay = document.getElementById('loadingOverlay');
  if (overlay) {
    if (subText) {
      const sub = overlay.querySelector('.spinner-sub');
      if (sub) sub.innerText = subText;
    }
    overlay.classList.remove('hidden');
  }
}

function hideLoadingOverlay() {
  const overlay = document.getElementById('loadingOverlay');
  if (overlay) {
    overlay.classList.add('hidden');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  setTimeout(hideLoadingOverlay, 250);

  // Attach loader to forms and country buttons
  const filterForm = document.getElementById('dashboardFilterForm');
  if (filterForm) {
    filterForm.addEventListener('submit', () => {
      showLoadingOverlay('Aplicando filtros y matcheando rutas...');
    });
  }

  document.querySelectorAll('a[href^="/"], a[href^="?"]').forEach(link => {
    link.addEventListener('click', (e) => {
      if (!e.ctrlKey && !e.metaKey && !link.target) {
        showLoadingOverlay('Cargando inteligencia de trayectos Mercotruck...');
      }
    });
  });
});

// Client Contact Modal Functions
let activeContactProspectId = null;

async function openClientContactModal(prospectId) {
  if (!prospectId) {
    const sel = document.getElementById('escProspectSelect');
    if (sel && sel.value) prospectId = parseInt(sel.value);
  }
  if (!prospectId) {
    alert('Por favor selecciona una empresa primero.');
    return;
  }

  activeContactProspectId = prospectId;
  const modal = document.getElementById('clientContactModal');
  if (modal) modal.classList.add('active');

  try {
    const res = await fetch(`/api/v1/prospects/${prospectId}/contacts`);
    if (!res.ok) throw new Error('Error al cargar datos del cliente');
    
    const data = await res.json();
    document.getElementById('modalClientName').innerText = data.name;
    document.getElementById('modalClientRut').innerText = `RUT / CUIT: ${data.tax_id}`;
    
    const googleQuery = encodeURIComponent(`${data.name} Chile Argentina telefono contacto logistica`);
    document.getElementById('modalGoogleLink').href = `https://www.google.com/search?q=${googleQuery}`;

    const listEl = document.getElementById('modalContactList');
    if (data.contacts && data.contacts.length > 0) {
      listEl.innerHTML = data.contacts.map(c => `
        <div style="background: var(--bg-card); border: 1px solid var(--border-color); padding: 0.85rem; border-radius: 0.5rem; margin-bottom: 0.5rem;">
          <div style="font-weight: 700; color: var(--accent-cyan); font-size: 0.95rem;">👤 ${c.name} (${c.role_title})</div>
          <div style="font-size: 0.85rem; margin-top: 0.3rem;">📞 Teléfono: <strong>${c.phone}</strong></div>
          <div style="font-size: 0.85rem; margin-top: 0.2rem;">✉️ Email: <strong>${c.email}</strong></div>
        </div>
      `).join('');
    } else {
      listEl.innerHTML = `
        <div style="background: rgba(245,158,11,0.1); border: 1px solid rgba(245,158,11,0.3); padding: 1rem; border-radius: 0.5rem; color: #fbbf24; font-size: 0.85rem;">
          ⚠️ <strong>Aviso Importante:</strong> Esta empresa aún no posee un teléfono/email directo registrado en el CRM.<br>
          <em>(Los archivos aduaneros de Softtrade no contienen datos de contacto directo por normativa aduanera).</em>
        </div>
      `;
    }
  } catch (err) {
    console.error('Error cargando contactos:', err);
  }
}

function closeClientContactModal() {
  const modal = document.getElementById('clientContactModal');
  if (modal) modal.classList.remove('active');
}

async function saveNewContact(event) {
  if (event) event.preventDefault();
  if (!activeContactProspectId) return;

  const name = document.getElementById('newContactName').value;
  const role = document.getElementById('newContactRole').value;
  const phone = document.getElementById('newContactPhone').value;
  const email = document.getElementById('newContactEmail').value;

  if (!name || (!phone && !email)) {
    alert('Ingresa el nombre del contacto y al menos un teléfono o email.');
    return;
  }

  try {
    const res = await fetch(`/api/v1/prospects/${activeContactProspectId}/contacts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name,
        role_title: role,
        phone: phone,
        email: email
      })
    });

    if (res.ok) {
      alert('✅ Contacto guardado con éxito');
      document.getElementById('newContactName').value = '';
      document.getElementById('newContactPhone').value = '';
      document.getElementById('newContactEmail').value = '';
      openClientContactModal(activeContactProspectId);
    }
  } catch (err) {
    console.error('Error guardando contacto:', err);
  }
}

// Interactive Map Locator (Official Google Maps JS API)
let googleMapInstance = null;
let directionsRenderer = null;

function openClientMapModal(itemJsonEncoded) {
  let item = null;
  try {
    item = typeof itemJsonEncoded === 'string' ? JSON.parse(decodeURIComponent(itemJsonEncoded)) : itemJsonEncoded;
  } catch(e) {
    console.error('Error parsing map payload:', e);
    return;
  }

  const modal = document.getElementById('clientMapModal');
  if (!modal) return;

  document.getElementById('mapClientTitle').innerText = item.name;
  document.getElementById('mapClientRouteSubtitle').innerText = `Corredor: ${item.origin_str || 'Origen'} ➔ ${item.destination_str || 'Destino'} | Operación: ${item.fuente}`;

  const oLat = parseFloat(item.origin_lat) || -32.890;
  const oLon = parseFloat(item.origin_lon) || -68.845;
  const dLat = parseFloat(item.dest_lat) || -33.459;
  const dLon = parseFloat(item.dest_lon) || -70.648;

  const gmapsLink = document.getElementById('modalGoogleMapsLink');
  if (gmapsLink) {
    gmapsLink.href = `https://www.google.com/maps/dir/?api=1&origin=${oLat},${oLon}&destination=${dLat},${dLon}&travelmode=driving`;
  }

  modal.classList.add('active');

  setTimeout(() => {
    initGoogleMap(item);
  }, 120);
}

function closeClientMapModal() {
  const modal = document.getElementById('clientMapModal');
  if (modal) modal.classList.remove('active');
}

function initGoogleMap(item) {
  const mapContainer = document.getElementById('googleMapContainer');
  if (!mapContainer) return;

  const oLat = parseFloat(item.origin_lat) || -32.890;
  const oLon = parseFloat(item.origin_lon) || -68.845;
  const dLat = parseFloat(item.dest_lat) || -33.459;
  const dLon = parseFloat(item.dest_lon) || -70.648;

  if (typeof google === 'undefined' || !google.maps) {
    mapContainer.innerHTML = `
      <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; color:var(--text-muted); text-align:center; padding:2rem; background:#0b1120;">
        <div style="font-size:2.5rem; margin-bottom:0.75rem;">🗺️</div>
        <h3 style="color:var(--text-main); font-size:1.1rem; margin-bottom:0.5rem; font-weight:700;">Google Maps API Key Requerida</h3>
        <p style="font-size:0.85rem; max-width:480px; margin-bottom:1.25rem; color:var(--text-muted); line-height:1.5;">
          Ingresa tu <strong>GOOGLE_MAPS_API_KEY</strong> en el archivo <code>.env</code> para habilitar la visualización interactiva del mapa nativo de Google Maps.
        </p>
        <a href="https://www.google.com/maps/dir/?api=1&origin=${oLat},${oLon}&destination=${dLat},${dLon}&travelmode=driving" target="_blank" class="btn-primary" style="font-size:0.85rem; padding:0.6rem 1.2rem;">
          🌐 Abrir ruta directamente en Google Maps
        </a>
      </div>
    `;
    return;
  }

  const originLatLng = { lat: oLat, lng: oLon };
  const destLatLng = { lat: dLat, lng: dLon };
  const centerLatLng = { lat: (oLat + dLat) / 2, lng: (oLon + dLon) / 2 };

  // Custom Dark Mode Styling matching Mercotruck Enterprise theme
  const darkMapStyle = [
    { elementType: "geometry", stylers: [{ color: "#0b1120" }] },
    { elementType: "labels.text.stroke", stylers: [{ color: "#0b1120" }] },
    { elementType: "labels.text.fill", stylers: [{ color: "#94a3b8" }] },
    { featureType: "administrative.locality", elementType: "labels.text.fill", stylers: [{ color: "#cbd5e1" }] },
    { featureType: "poi", elementType: "labels.text.fill", stylers: [{ color: "#06b6d4" }] },
    { featureType: "poi.park", elementType: "geometry", stylers: [{ color: "#0f172a" }] },
    { featureType: "road", elementType: "geometry", stylers: [{ color: "#1e293b" }] },
    { featureType: "road", elementType: "geometry.stroke", stylers: [{ color: "#0f172a" }] },
    { featureType: "road", elementType: "labels.text.fill", stylers: [{ color: "#64748b" }] },
    { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#334155" }] },
    { featureType: "road.highway", elementType: "geometry.stroke", stylers: [{ color: "#0f172a" }] },
    { featureType: "road.highway", elementType: "labels.text.fill", stylers: [{ color: "#f8fafc" }] },
    { featureType: "water", elementType: "geometry", stylers: [{ color: "#0284c7" }] },
    { featureType: "water", elementType: "labels.text.fill", stylers: [{ color: "#38bdf8" }] }
  ];

  googleMapInstance = new google.maps.Map(mapContainer, {
    zoom: 6,
    center: centerLatLng,
    styles: darkMapStyle,
    disableDefaultUI: false,
    zoomControl: true,
    mapTypeControl: false,
    streetViewControl: false
  });

  // Markers
  const originMarker = new google.maps.Marker({
    position: originLatLng,
    map: googleMapInstance,
    title: `ORIGEN: ${item.origin_str || 'Origen'}`,
    icon: {
      url: 'https://maps.google.com/mapfiles/ms/icons/cyan-dot.png'
    }
  });

  const destMarker = new google.maps.Marker({
    position: destLatLng,
    map: googleMapInstance,
    title: `DESTINO: ${item.destination_str || 'Destino'}`,
    icon: {
      url: 'https://maps.google.com/mapfiles/ms/icons/red-dot.png'
    }
  });

  const originInfoWindow = new google.maps.InfoWindow({
    content: `
      <div style="color: #0f172a; font-family: sans-serif; padding: 4px;">
        <strong style="color: #0284c7;">🚛 ORIGEN: ${item.origin_str || 'Origen'}</strong><br>
        <b>Empresa:</b> ${item.name || 'Cliente'}<br>
        <b>Camiones:</b> ${item.total_trucks || 1}
      </div>
    `
  });

  const destInfoWindow = new google.maps.InfoWindow({
    content: `
      <div style="color: #0f172a; font-family: sans-serif; padding: 4px;">
        <strong style="color: #059669;">📍 DESTINO: ${item.destination_str || 'Destino'}</strong><br>
        <b>Flete Competencia:</b> ${item.avg_freight_per_truck_usd || 'N/A'}
      </div>
    `
  });

  originMarker.addListener('click', () => originInfoWindow.open(googleMapInstance, originMarker));
  destMarker.addListener('click', () => destInfoWindow.open(googleMapInstance, destMarker));

  // Route calculation with DirectionsService
  const directionsService = new google.maps.DirectionsService();
  if (directionsRenderer) {
    directionsRenderer.setMap(null);
  }

  directionsRenderer = new google.maps.DirectionsRenderer({
    map: googleMapInstance,
    suppressMarkers: true,
    polylineOptions: {
      strokeColor: "#06b6d4",
      strokeWeight: 5,
      strokeOpacity: 0.85
    }
  });

  directionsService.route(
    {
      origin: originLatLng,
      destination: destLatLng,
      travelMode: google.maps.TravelMode.DRIVING
    },
    (result, status) => {
      if (status === google.maps.DirectionsStatus.OK) {
        directionsRenderer.setDirections(result);
      } else {
        // Fallback: geodesic polyline if Directions API returns ZERO_RESULTS or key restricted
        const routePath = new google.maps.Polyline({
          path: [originLatLng, destLatLng],
          geodesic: true,
          strokeColor: "#06b6d4",
          strokeOpacity: 0.85,
          strokeWeight: 4
        });
        routePath.setMap(googleMapInstance);

        const bounds = new google.maps.LatLngBounds();
        bounds.extend(originLatLng);
        bounds.extend(destLatLng);
        googleMapInstance.fitBounds(bounds);
      }
    }
  );

  // Fetch Live Google Places Intelligence Data
  fetchGooglePlacesData(item, googleMapInstance);
}

// Google Places Live Intelligence Fetcher
let lastFetchedPlacesData = null;

function fetchGooglePlacesData(item, googleMapInstance) {
  const loadingEl = document.getElementById('placesLoading');
  const emptyEl = document.getElementById('placesEmpty');
  const contentEl = document.getElementById('placesContent');
  const copyBtn = document.getElementById('placesCopyContactBtn');

  if (loadingEl) loadingEl.style.display = 'block';
  if (emptyEl) emptyEl.style.display = 'none';
  if (contentEl) contentEl.style.display = 'none';
  if (copyBtn) copyBtn.style.display = 'none';

  if (typeof google === 'undefined' || !google.maps || !google.maps.places) {
    if (loadingEl) loadingEl.style.display = 'none';
    if (emptyEl) emptyEl.style.display = 'block';
    return;
  }

  const dummyDiv = document.createElement('div');
  const service = new google.maps.places.PlacesService(googleMapInstance || dummyDiv);
  const queryStr = `${item.name} ${item.origin_str || ''}`.trim();

  service.textSearch({ query: queryStr }, (results, status) => {
    if (status === google.maps.places.PlacesServiceStatus.OK && results && results.length > 0) {
      const firstResult = results[0];
      
      service.getDetails({
        placeId: firstResult.place_id,
        fields: ['name', 'formatted_address', 'formatted_phone_number', 'international_phone_number', 'website', 'rating', 'user_ratings_total', 'photos', 'address_components', 'url']
      }, (place, detailStatus) => {
        if (loadingEl) loadingEl.style.display = 'none';

        if (detailStatus === google.maps.places.PlacesServiceStatus.OK && place) {
          lastFetchedPlacesData = {
            name: place.name || item.name,
            address: place.formatted_address || 'Sin dirección registrada',
            phone: place.formatted_phone_number || place.international_phone_number || '',
            website: place.website || place.url || '',
            rating: place.rating || null,
            reviews: place.user_ratings_total || 0,
            city: extractCityFromAddressComponents(place.address_components) || item.origin_str || '—'
          };
          renderGooglePlacesData(lastFetchedPlacesData, place);
        } else {
          lastFetchedPlacesData = {
            name: firstResult.name || item.name,
            address: firstResult.formatted_address || 'Sin dirección registrada',
            phone: '',
            website: '',
            rating: firstResult.rating || null,
            reviews: firstResult.user_ratings_total || 0,
            city: item.origin_str || '—'
          };
          renderGooglePlacesData(lastFetchedPlacesData, firstResult);
        }
      });
    } else {
      if (loadingEl) loadingEl.style.display = 'none';
      if (emptyEl) {
        emptyEl.style.display = 'block';
        emptyEl.innerHTML = `
          <div style="font-size: 1.8rem; margin-bottom: 0.4rem;">🏬</div>
          <div style="font-weight:700; color:var(--text-main); margin-bottom:0.2rem;">${item.name}</div>
          <div style="font-size:0.775rem;">Ubicación: ${item.origin_str || 'Origen'}</div>
        `;
      }
    }
  });
}

function extractCityFromAddressComponents(components) {
  if (!components || !Array.isArray(components)) return null;
  for (const c of components) {
    if (c.types.includes('locality') || c.types.includes('administrative_area_level_2')) {
      return c.long_name;
    }
  }
  for (const c of components) {
    if (c.types.includes('administrative_area_level_1')) {
      return c.long_name;
    }
  }
  return null;
}

function renderGooglePlacesData(data, placeObj) {
  const contentEl = document.getElementById('placesContent');
  const copyBtn = document.getElementById('placesCopyContactBtn');
  if (!contentEl) return;

  document.getElementById('placesName').innerText = data.name;
  
  const ratingEl = document.getElementById('placesRating');
  const reviewsEl = document.getElementById('placesReviews');
  if (data.rating) {
    ratingEl.innerText = `⭐ ${data.rating.toFixed(1)} / 5.0`;
    reviewsEl.innerText = `(${data.reviews} opiniones en Google)`;
  } else {
    ratingEl.innerText = `⭐ Sin calificaciones en Google`;
    reviewsEl.innerText = ``;
  }

  document.getElementById('placesAddress').innerText = data.address;
  document.getElementById('placesCity').innerText = `🏙️ ${data.city}`;

  const phoneLink = document.getElementById('placesPhoneLink');
  if (data.phone) {
    phoneLink.innerText = data.phone;
    phoneLink.href = `tel:${data.phone.replace(/[^0-9+]/g, '')}`;
    phoneLink.style.color = '#60a5fa';
  } else {
    phoneLink.innerText = 'No publicado en Google Maps';
    phoneLink.href = '#';
    phoneLink.style.color = 'var(--text-muted)';
  }

  const websiteContainer = document.getElementById('placesWebsiteContainer');
  const websiteLink = document.getElementById('placesWebsiteLink');
  if (data.website) {
    websiteContainer.style.display = 'block';
    websiteLink.href = data.website;
    try {
      const urlObj = new URL(data.website);
      websiteLink.innerText = `🌐 ${urlObj.hostname}`;
    } catch(e) {
      websiteLink.innerText = `🌐 ${data.website}`;
    }
  } else {
    websiteContainer.style.display = 'none';
  }

  // Photo
  const photoContainer = document.getElementById('placesPhotoContainer');
  const photoEl = document.getElementById('placesPhoto');
  if (placeObj && placeObj.photos && placeObj.photos.length > 0) {
    try {
      const photoUrl = placeObj.photos[0].getUrl({ maxWidth: 400, maxHeight: 220 });
      photoEl.src = photoUrl;
      photoContainer.style.display = 'block';
    } catch(e) {
      photoContainer.style.display = 'none';
    }
  } else {
    photoContainer.style.display = 'none';
  }

  contentEl.style.display = 'block';
  if (copyBtn) copyBtn.style.display = 'block';
}

function copyPlacesContactToForm() {
  if (!lastFetchedPlacesData) return;

  closeClientMapModal();

  const phoneInput = document.getElementById('newContactPhone');
  const nameInput = document.getElementById('newContactName');
  const modalClientName = document.getElementById('modalClientName');

  if (modalClientName) {
    modalClientName.innerText = `Ficha de Contacto — ${lastFetchedPlacesData.name}`;
  }

  if (phoneInput && lastFetchedPlacesData.phone) {
    phoneInput.value = lastFetchedPlacesData.phone;
  }
  if (nameInput) {
    nameInput.value = `Contacto Principal (${lastFetchedPlacesData.city})`;
  }

  const contactModal = document.getElementById('clientContactModal');
  if (contactModal) {
    contactModal.classList.add('active');
  }
}

function toggleRowDetail(rowId) {
  const detailRow = document.getElementById(`detail-${rowId}`);
  const chev = document.getElementById(`chev-${rowId}`);
  if (!detailRow) return;
  if (detailRow.style.display === 'none' || !detailRow.style.display) {
    detailRow.style.display = 'table-row';
    if (chev) chev.classList.add('open');
    fetchGooglePlacesIntel(rowId);
  } else {
    detailRow.style.display = 'none';
    if (chev) chev.classList.remove('open');
  }
}

function fetchGooglePlacesIntel(rowId) {
  const gBox = document.getElementById(`gIntel-${rowId}`);
  if (!gBox || gBox.getAttribute('data-loaded') === 'true') return;

  const companyName = gBox.getAttribute('data-name') || '';
  const country = gBox.getAttribute('data-country') || 'CHILE';
  const searchQuery = `${companyName} ${country}`;

  if (window.google && google.maps && google.maps.places) {
    try {
      const dummyDiv = document.createElement('div');
      const service = new google.maps.places.PlacesService(dummyDiv);

      service.textSearch({ query: searchQuery }, (results, status) => {
        if (status === google.maps.places.PlacesServiceStatus.OK && results && results.length > 0) {
          const place = results[0];
          const rating = place.rating ? `${place.rating} ★ (${place.user_ratings_total || 0})` : 'Sin reseñas';
          const address = place.formatted_address || 'Dirección detectada';

          service.getDetails({ placeId: place.place_id, fields: ['formatted_phone_number', 'website', 'url', 'rating', 'formatted_address'] }, (detail, statusDetail) => {
            gBox.setAttribute('data-loaded', 'true');
            const phone = detail && detail.formatted_phone_number ? detail.formatted_phone_number : null;
            const website = detail && detail.website ? detail.website : null;
            const googleUrl = detail && detail.url ? detail.url : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(searchQuery)}`;

            let phoneHtml = phone 
              ? `<a href="tel:${phone}" style="color: var(--accent-cyan); font-weight: 700; text-decoration: none;">📞 ${phone}</a>`
              : `<span style="color: var(--text-muted);">📞 Teléfono no informado</span>`;

            let webHtml = website 
              ? `<a href="${website}" target="_blank" style="color: #3b82f6; font-weight: 700; text-decoration: none; word-break: break-all;">🌐 ${website.replace(/^https?:\/\//, '').replace(/\/$/, '')}</a>`
              : `<span style="color: var(--text-muted);">🌐 Sitio Web no informado</span>`;

            gBox.innerHTML = `
              <div style="background: rgba(27, 94, 107, 0.08); border: 1px solid rgba(27, 94, 107, 0.2); border-radius: 8px; padding: 10px 12px; margin-top: 8px; font-size: 0.8rem;">
                <div style="font-weight: 800; color: #134552; margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center;">
                  <span>📍 Datos Verificados Google Places</span>
                  <span style="color: #f59e0b; font-weight: 700; font-size: 0.775rem;">⭐ ${rating}</span>
                </div>
                <div style="margin-bottom: 4px; color: var(--text-main); font-size: 0.775rem;">🏢 ${address}</div>
                <div style="display: flex; gap: 12px; flex-wrap: wrap; margin-top: 6px; font-size: 0.775rem; border-top: 1px solid rgba(0,0,0,0.06); padding-top: 6px;">
                  ${phoneHtml}
                  ${webHtml}
                  <a href="${googleUrl}" target="_blank" style="color: var(--text-muted); font-size: 0.725rem; text-decoration: underline;">🗺️ Abrir en Maps</a>
                </div>
              </div>
            `;
          });
        } else {
          renderFallbackIntel(gBox, companyName, country);
        }
      });
      return;
    } catch (e) {
      console.warn("Google Places API search warning:", e);
    }
  }

  renderFallbackIntel(gBox, companyName, country);
}

function renderFallbackIntel(gBox, companyName, country) {
  gBox.setAttribute('data-loaded', 'true');
  const searchUrl = `https://www.google.com/search?q=${encodeURIComponent(companyName + ' ' + country + ' telefono contacto logistica')}`;
  const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(companyName + ' ' + country)}`;

  gBox.innerHTML = `
    <div style="background: rgba(27, 94, 107, 0.05); border: 1px solid rgba(27, 94, 107, 0.15); border-radius: 8px; padding: 10px 12px; margin-top: 8px; font-size: 0.8rem;">
      <div style="font-weight: 800; color: #134552; margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center;">
        <span>📍 Inteligencia Comercial</span>
        <span style="color: var(--text-muted); font-size: 0.725rem;">Acceso Directo</span>
      </div>
      <div style="display: flex; gap: 10px; flex-wrap: wrap; font-size: 0.775rem; margin-top: 4px;">
        <a href="${searchUrl}" target="_blank" style="color: var(--accent-cyan); font-weight: 700; text-decoration: none;">🔍 Buscar Teléfono & Web</a>
        <a href="${mapsUrl}" target="_blank" style="color: #3b82f6; font-weight: 700; text-decoration: none;">🗺️ Abrir en Google Maps</a>
      </div>
    </div>
  `;
}

function setCountryFilter(countryCode) {
  showLoadingOverlay('Filtrando por ' + (countryCode || 'Todos') + '...');
  const form = document.querySelector('form.filters-bar');
  let countryInput = document.getElementById('filterCountryInput');
  if (!countryInput && form) {
    countryInput = document.createElement('input');
    countryInput.type = 'hidden';
    countryInput.name = 'country';
    countryInput.id = 'filterCountryInput';
    form.appendChild(countryInput);
  }
  if (countryInput) {
    countryInput.value = countryCode;
  }
  if (form) {
    form.submit();
  }
}

function copyScriptToClipboard(btn, text) {
  if (!navigator.clipboard) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    document.body.appendChild(textArea);
    textArea.select();
    document.execCommand('copy');
    document.body.removeChild(textArea);
  } else {
    navigator.clipboard.writeText(text);
  }
  if (btn) {
    const origText = btn.innerHTML;
    btn.innerHTML = '✓ ¡Script Copiado!';
    btn.style.background = 'var(--accent-emerald)';
    btn.style.color = '#fff';
    setTimeout(() => {
      btn.innerHTML = origText;
      btn.style.background = '';
      btn.style.color = '';
    }, 2000);
  }
}

// Global Exports
window.openClientMapModal = openClientMapModal;
window.closeClientMapModal = closeClientMapModal;
window.openClientContactModal = openClientContactModal;
window.closeClientContactModal = closeClientContactModal;
window.copyPlacesContactToForm = copyPlacesContactToForm;
window.toggleRowDetail = toggleRowDetail;
window.setCountryFilter = setCountryFilter;
window.copyScriptToClipboard = copyScriptToClipboard;
