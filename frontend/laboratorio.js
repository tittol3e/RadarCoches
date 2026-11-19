'use strict';

const labApi = '/api/lab';
const labPrice = cents => cents == null ? 'Desconocido' : euro(cents / 100);
const labValue = value => value ?? 'Desconocido';

function labAds(records) {
  if (!records.length) return txt('p', 'Sin anuncios en esta etapa.', 'subtle');
  return table(['Fuente', 'ID', 'Marca', 'Modelo', 'Año', 'Km', 'Precio', 'Versión'],
    records.map(row => [row.source, row.id, labValue(row.marca), labValue(row.modelo),
      labValue(row.anio), row.kilometros == null ? 'Desconocidos' : num(row.kilometros),
      labPrice(row.precio_centimos), labValue(row.version_evento ?? row.version)]));
}

function labHistory(rows) {
  if (!rows.length) return txt('p', 'Sin eventos registrados.', 'subtle');
  return table(['Fuente / ID', 'Vehículo', 'Versión', 'Evento', 'Precio anterior', 'Precio nuevo'],
    rows.map(row => [row.source + ' / ' + row.id, row.ad.marca + ' ' + row.ad.modelo, row.version,
      el('span', {title: row.event_id, text: row.kind === 'created' ? 'Alta' : 'Actualización'}),
      row.kind === 'created' && row.old_price == null ? 'No corresponde' : labPrice(row.old_price),
      labPrice(row.new_price)]));
}

const labChanges = rows => rows.filter(row => row.old_price != null && row.new_price != null && row.old_price !== row.new_price);
const labLink = (path, label) => el('a', {href: path, target: '_blank', rel: 'noopener', text: label});
const labJSON = data => txt('pre', JSON.stringify(data, null, 2), 'lab-json');
const labDetails = (title, ...content) => el('details', {}, [txt('summary', title), ...content]);

async function laboratorio() {
  const root = el('div', {class: 'lab-page'}, [
    head('Laboratorio de datos', 'Demostración de ingesta con dos fuentes de anuncios sintéticos.'),
    notice('Los anuncios de esta práctica se guardan en bases separadas del Radar personal.', 'demo')
  ]);
  const [practices, reports] = await Promise.all([api(labApi + '/practices'), api(labApi + '/distributed')]);
  const local = panel('Demostración de ingesta · Laboratorio local con SQLite', [
    txt('p', 'Dos APIs FastAPI se consultan dentro de la aplicación. SQLite guarda la cola, los anuncios y su historial.')
  ]);
  const selected = el('select', {'aria-label': 'Práctica local guardada'});
  const content = el('div');
  const feedback = el('div', {'role': 'status'});
  const newButton = btn('Nueva práctica limpia', async () => {
    const {id} = await api(labApi + '/practices', 'POST', {});
    selected.append(el('option', {value: id, text: 'Práctica ' + id.slice(0, 8)}));
    selected.value = id;
    await loadPractice();
  });
  selected.append(el('option', {value: '', text: 'Selecciona una práctica guardada'}));
  for (const row of practices) selected.append(el('option', {value: row.id,
    text: date(row.saved) + ' · ' + row.id.slice(0, 8)}));
  selected.addEventListener('change', loadPractice);
  local.append(el('div', {class: 'lab-select'}, [newButton, selected]), feedback, content);
  const distributed = distributedLab(reports);
  root.append(el('div', {class: 'lab-shortcuts'}, [
    btn('Ir a la práctica SQLite', () => local.scrollIntoView(), 'secondary'),
    btn('Ver evidencias distribuidas', () => distributed.scrollIntoView(), 'secondary')
  ]), local, distributed, previousLab());
  selected.value = practices[0]?.id || '';
  await loadPractice();
  return root;

  async function loadPractice() {
    const id = selected.value;
    feedback.replaceChildren();
    content.replaceChildren();
    if (!id) {
      content.append(txt('p', 'Crea una práctica para empezar con las fuentes y el almacenamiento vacíos.'));
      return;
    }
    const base = labApi + '/practices/' + id;
    try {
      const data = await api(base);
      if (selected.value === id) renderPractice(base, data);
    } catch (error) {
      if (selected.value === id) feedback.replaceChildren(notice(error.message, 'error'));
    }
  }

  function renderPractice(base, data) {
    const c = data.counts;
    const replay = data.runs.find(run => run.details?.stage === 'replay');
    const verified = (stage, revision) => data.runs.some(({status, details}) =>
      status === 'success' && details?.stage === stage && details.revision === revision &&
      Object.keys(details.checks || {}).length && Object.values(details.checks).every(Boolean));
    const initialPrepared = data.revision >= 0;
    const initialExtracted = verified('extract', 0);
    const initialStored = verified('store', 0);
    const firstRevision = verified('revision', 1);
    const secondRevision = verified('revision', 2);
    const steps = [
      ['Leer las APIs', 'Preparar y consultar los inventarios iniciales de las dos fuentes.', '/stage/read', !initialPrepared],
      ['Extraer los eventos', 'Leer /changes por páginas y guardar los eventos en la cola.', '/stage/extract', initialPrepared && !initialExtracted],
      ['Procesar y almacenar', 'Entregar la cola al consumidor SQLite y consultar las fichas guardadas.', '/stage/store', initialExtracted && !initialStored],
      ['Incorporar anuncios nuevos', 'Ejecutar la revisión 1 y localizar las altas.', '/revision/1', initialStored && !firstRevision],
      ['Actualizar precios', 'Ejecutar la revisión 2 y consultar los precios anterior y nuevo.', '/revision/2', firstRevision && !secondRevision],
      ['Reprocesar y verificar', 'Leer la revisión 3 y volver a entregar la cola guardada al consumidor local.', '/revision/3', secondRevision && !replay?.details?.passed]
    ];
    const controls = el('ol', {class: 'lab-steps'}, steps.map(([title, explanation, path, enabled], index) => {
      const completed = [initialPrepared, initialExtracted, initialStored, firstRevision,
        secondRevision, replay?.details?.passed][index];
      const button = btn(title, async () => {
        newButton.disabled = selected.disabled = true;
        feedback.replaceChildren(notice('Ejecutando el paso en SQLite…'));
        try {
          const result = await api(base + path, 'POST', {});
          renderPractice(base, result);
          const details = result.runs[0]?.details;
          const failed = details?.passed === false || Object.values(details?.checks || {}).includes(false);
          feedback.replaceChildren(notice(failed ? 'Alguna verificación falló. Consulta el informe.' :
            'Paso terminado. Consulta los datos y el registro de operaciones.', failed ? 'error' : 'good'));
        } catch (error) {
          await loadPractice();
          feedback.replaceChildren(notice(error.message, 'error'));
        } finally {
          newButton.disabled = selected.disabled = false;
        }
      }, 'secondary');
      button.disabled = !enabled;
      return el('li', {}, [el('div', {}, [txt('strong', title), txt('small', explanation),
        completed ? badge('Completado', 'good') : null]), enabled ? button : null]);
    }));

    const sources = el('div', {class: 'grid two'}, ['demo_a', 'demo_b'].map(source => {
      const target = el('div');
      async function loadSource() {
          try {
            const response = await api(base + '/sources/' + source);
            const ads = response['/ads'].body;
            target.replaceChildren(notice(`/health · HTTP ${response['/health'].status} · ${response['/health'].body.status}`, 'good'),
              txt('p', `/ads · HTTP ${response['/ads'].status} · ${ads.total} anuncios · Página ${ads.page}`),
              labAds(ads.items), labDetails('Ver respuestas JSON de los tres endpoints', labJSON(response)));
          } catch (error) {
            target.replaceChildren(notice('Fuente no disponible. ' + error.message, 'error'));
          }
      }
      if (initialPrepared) loadSource();
      return el('div', {class: 'quote-card'}, [txt('h3', source),
        txt('p', 'Inventario sintético independiente. /ads devuelve fichas vigentes y /changes devuelve altas y versiones ordenadas por cursor.'),
        btn('Consultar API ' + source, loadSource, 'secondary'), target]);
    }));

    const totals = el('div', {class: 'grid three'}, [
      metric('Anuncios únicos', num(c.ads), 'Una ficha por fuente e ID'),
      metric('Cambios de precio', num(c.price_updates), 'Versiones con distinto precio'),
      metric('Eventos generados', num(c.source_changes), 'Altas y actualizaciones en las APIs'),
      metric('Eventos extraídos', num(c.outbox), 'Eventos distintos en la cola SQLite'),
      metric('Eventos entregados', num(c.delivered), 'Confirmados en la cola local'),
      metric('Eventos procesados', num(c.consumed), `${num(c.pending)} pendientes en la cola`)
    ]);
    const runs = data.runs.filter(row => row.details?.stage !== 'replay');
    const stageNames = {extract: 'Extracción', store: 'Almacenamiento', revision: 'Revisión'};
    const history = data.history;
    const additions = [...runs].reverse().flatMap(run => run.details?.new_records ?? []);
    const sourcesTitle = txt('h3', 'Respuestas de las APIs');
    const recordsTitle = txt('h3', 'Anuncios guardados');
    const pricesTitle = txt('h3', 'Cambios de precio');
    const evidenceTitle = txt('h3', 'Operaciones y evidencias');
    const queue = labDetails('Ver eventos recogidos en la cola',
      data.events.length ? table(['Cursor', 'Fuente / ID', 'Evento', 'Versión', 'Precio'], [...data.events].reverse().map(event => [
        event.seq, event.source + ' / ' + event.ad.id, event.kind === 'created' ? 'Alta' : 'Actualización',
        event.ad.version_evento, labPrice(event.ad.precio_centimos)])) : txt('p', 'La cola está vacía.'),
      txt('p', 'Último cursor extraído por fuente. ' + JSON.stringify(data.cursors), 'subtle'));
    if (initialExtracted && !initialStored) queue.open = true;
    const shortcuts = el('div', {class: 'lab-shortcuts'},
      [[sourcesTitle, 'APIs'], [queue, 'Cola'], [recordsTitle, 'Anuncios'],
        [pricesTitle, 'Precios'], [evidenceTitle, 'Verificaciones']].map(([target, label]) =>
        btn(label, () => {
          if (target === queue) queue.open = true;
          target.scrollIntoView();
        }, 'ghost')));

    content.replaceChildren(controls, shortcuts, sourcesTitle,
      txt('p', 'Una API es una ruta que devuelve datos estructurados a otro programa. Consulta aquí las respuestas reales de las dos fuentes en proceso.'),
      sources, txt('h3', 'Estado acumulado de la práctica'), totals,
      recordsTitle, labAds(data.records),
      txt('h3', 'Altas después del inventario inicial'), labAds(additions),
      pricesTitle, labHistory(labChanges(history)),
      labDetails('Ver historial completo de versiones', labHistory(history)),
      queue, evidenceTitle,
      runs.length ? table(['Operación', 'Estado', 'Extraídos', 'Entregados / recibidos', 'Procesados', 'Nuevos', 'Cambios de precio', 'Únicos', 'Verificación'],
        [...runs].reverse().map(({status, details: d}) => [
          d?.stage ? stageNames[d.stage] + (d.stage === 'revision' ? ' ' + d.revision : '') : 'Ejecución',
          ({success: 'Completada', interrupted: 'Interrumpida', failed: 'Fallida', running: 'En curso'})[status] ?? status,
          ...['extracted', 'delivered', 'processed', 'new_ads', 'price_updates', 'ads'].map(key => d?.[key] ?? 'No disponible'),
          Object.keys(d?.checks || {}).length ? (Object.values(d.checks).every(Boolean) ? 'Superada' : 'Fallida') : 'Sin verificación'
        ])) : txt('p', 'Aún no hay operaciones guardadas.'),
      replay ? notice(replay.details.passed
        ? `Reenvío verificado · ${replay.details.received} eventos recibidos · ${replay.details.processed} eventos nuevos · ${replay.details.ads_before} → ${replay.details.ads} anuncios únicos.`
        : 'La verificación del reenvío falló. Consulta el informe.', replay.details.passed ? 'good' : 'error') : null,
      labLink(base + '/report', 'Descargar informe de esta práctica (JSON)'),
      labDetails('Prueba local de volumen', txt('p', 'Ejercicio independiente con 1.000 anuncios iniciales.'),
        volumeTest()));
  }
}

function previousLab() {
  const output = el('div');
  return labDetails('Consultar la base local de ejercicios anteriores',
    txt('p', 'Inventario compartido de las revisiones ejecutadas desde la consola o desde la pantalla anterior.'),
    btn('Cargar resultados anteriores', async () => {
      const data = await api(labApi);
      output.replaceChildren(labAds(data.records), labDetails('Historial anterior', labHistory(data.history)));
    }, 'secondary'), output);
}

function volumeTest() {
  const output = el('div', {role: 'status'});
  return el('div', {}, [btn('Comprobar con 1.000 anuncios', async () => {
    output.replaceChildren(txt('p', 'Ejecutando la prueba de volumen…'));
    const result = await api(labApi + '/volume', 'POST', {});
    output.replaceChildren(notice(
      `${result.passed ? 'Prueba de volumen superada' : 'Prueba de volumen fallida'} · ${num(result.initial)} iniciales · ${num(result.final)} finales · ${num(result.price_updates)} cambios de precio.`,
      result.passed ? 'good' : 'error'),
      labLink(labApi + '/volume/' + result.id + '/report', 'Descargar informe de volumen (JSON)'));
  }, 'secondary'), output]);
}

function distributedLab(reports) {
  const selected = el('select', {'aria-label': 'Evidencia histórica distribuida'});
  selected.append(el('option', {value: '', text: 'Selecciona un informe guardado'}));
  for (const entry of reports) selected.append(el('option', {value: entry.id,
    text: date(entry.saved) + ' · ' + entry.id.slice(0, 8) + (entry.passed ? ' · Superada' : ' · Fallida')}));
  const output = el('div', {'aria-live': 'polite'});
  let request = 0;
  selected.addEventListener('change', async () => {
    const token = ++request;
    const id = selected.value;
    output.replaceChildren();
    if (!id) return;
    const base = labApi + '/distributed/' + id;
    try {
      const report = await api(base + '/report');
      if (token !== request) return;
      const passed = report.passed === true && report.phase === 'completed';
      output.append(notice(passed ? 'Ejecución histórica superada' : 'Ejecución histórica sin superar · ' + labValue(report.phase), passed ? 'good' : 'warn'));
      output.append(labLink(base + '/report', 'Abrir informe original (JSON)'));
      if (report.error) output.append(notice(report.error, 'error'));
      const rows = (report.steps || []).map(step => [
        step.label, step.extraction?.landing_events_relayed ?? 'No disponible',
        step.published?.published ?? 'No disponible', step.consumed?.consumed ?? 'No disponible',
        step.verification?.events ?? 'No disponible', step.verification?.unique_ads ?? 'No disponible',
        step.verification?.passed ? 'Superada' : 'Sin verificación'
      ]);
      if (rows.length) output.append(table(['Etapa', 'Eventos en landing', 'Enviados', 'Recibidos', 'Eventos únicos procesados', 'Anuncios únicos', 'Verificación'], rows));
      if (report.replay) output.append(txt('p', `Replay con otro grupo de Kafka · ${num(report.replay.consumed)} mensajes recibidos · ${num(report.replay_verification?.unique_ads)} anuncios únicos tras el replay.`));
      if (!passed) return;
      const artifacts = await api(base + '/artifacts');
      if (token !== request) return;
      for (const [key, name] of [['duckdb', 'DuckDB · Anuncios finales'], ['parquet', 'Parquet · Anuncios finales']]) {
        const artifact = artifacts[key];
        output.append(txt('h3', name), artifact.available
          ? el('div', {}, [txt('p', `Mostrando ${num(artifact.records.length)} de ${num(artifact.total)} anuncios.`, 'subtle'), labAds(artifact.records)])
          : notice(artifact.message, 'warn'));
        if (artifact.history) output.append(txt('h3', 'Cambios de precio registrados en DuckDB'),
          labHistory(artifact.price_changes), labDetails(`Ver historial de eventos en DuckDB (${num(artifact.history.length)} de ${num(artifact.history_total)})`, labHistory(artifact.history)));
      }
    } catch (error) {
      if (token === request) output.append(notice(error.message, 'error'));
    }
  });
  return panel('Integración distribuida · Evidencias guardadas', [
    txt('p', 'dlt extrae desde las dos APIs HTTP y carga los eventos en DuckDB de entrada. La cola persistente espera la confirmación de Kafka. El consumidor procesa los mensajes y proyecta los resultados a DuckDB y Parquet.'),
    notice('Este visor consulta archivos históricos. El estado actual de Kafka y de las APIs HTTP se comprueba al ejecutar la integración.', 'info'),
    txt('p', 'Con Docker Desktop abierto, arranca Kafka y ejecuta la prueba desde PowerShell.'),
    labJSONCommands(),
    reports.length ? selected : notice('No hay informes distribuidos disponibles.', 'warn'),
    output
  ]);
}

function labJSONCommands() {
  return txt('pre', 'docker compose -f .\\actividad_ingesta\\docker-compose.yml up -d\n' +
    'powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\iniciar_ingesta.ps1 -Modo distributed', 'lab-json');
}
