/**
 * USIS chrome language (English / Español).
 * Persists in localStorage so the choice survives refresh and is not limited to /construction/.
 */
(function (global) {
	"use strict";

	var KEY = "usis.language";
	var COOKIE = "language";
	var applying = false;

	var ES = {
		USIS: "USIS",
		Dashboard: "Inicio",
		Leads: "Prospectos",
		Lead: "Prospecto",
		Estimate: "Estimación",
		"GS Plan": "Plan GS",
		Projects: "Proyectos",
		Calendar: "Calendario",
		Safety: "Seguridad",
		Documents: "Documentos",
		Email: "Correo",
		Messages: "Mensajes",
		"New message": "Mensaje nuevo",
		"Search people": "Buscar personas",
		"Type a message": "Escribe un mensaje",
		"Select a person to start chatting.": "Elige a alguien para chatear.",
		"No conversations yet.": "Aún no hay conversaciones.",
		HR: "RH",
		Applications: "Solicitudes",
		"HR suite": "Suite de RH",
		"HR dashboard": "Panel de RH",
		"Time sheets": "Hojas de tiempo",
		Expenses: "Gastos",
		Playbooks: "Guías",
		"User admin": "Admin. de usuarios",
		Procurement: "Compras",
		Purchasing: "Compras",
		Construction: "Construcción",
		Invoices: "Facturas",
		"Invoice approvals": "Aprobación de facturas",
		Reports: "Reportes",
		Search: "Buscar",
		"Report a problem": "Reportar un problema",
		"My profile": "Mi perfil",
		Language: "Idioma",
		Appearance: "Apariencia",
		Light: "Claro",
		Dark: "Oscuro",
		"Menus and login use this language.": "Los menús e inicio de sesión usan este idioma.",
		Logout: "Cerrar sesión",
		"Logout ": "Cerrar sesión",
		Login: "Iniciar sesión",
		"Sign in": "Iniciar sesión",
		"Sign in to CM": "Entrar a CM",
		"Sign in with Microsoft": "Entrar con Microsoft",
		"Sign out": "Cerrar sesión",
		Cancel: "Cancelar",
		Save: "Guardar",
		Create: "Crear",
		Send: "Enviar",
		Close: "Cerrar",
		Edit: "Editar",
		Delete: "Eliminar",
		Home: "Inicio",
		"No notifications.": "No hay notificaciones.",
		"See all notifications": "Ver todas las notificaciones",
		"Remember me": "Recordarme",
		"Forgot Password?": "¿Olvidó su contraseña?",
		"Email or username": "Correo o usuario",
		Password: "Contraseña",
		"Enter your password": "Escriba su contraseña",
		"USIS Construction Management": "USIS Control de Obra",
		"Sign in to access projects, estimates, and field operations.":
			"Inicie sesión para ver proyectos, estimaciones y trabajo de campo.",
		"Need a staff account?": "¿Necesita una cuenta de personal?",
		"Create one": "Crear una",
		"Looking for a job with USIS?": "¿Busca trabajo en USIS?",
		"Apply to USIS": "Solicitar en USIS",
		"Or sign in with": "O entre con",
		"Continue your application": "Continúe su solicitud",
		"Continue job application": "Continuar solicitud de empleo",
		"Email or username and password are required.": "Se requieren correo o usuario y contraseña.",
		"Invalid email, username, or password. On Render, create a user with the bootstrap script or register first.":
			"Correo, usuario o contraseña incorrectos.",
		"Email and password are required.": "Se requieren correo y contraseña.",
		"Invalid email or password. On Render, create a user with the bootstrap script or register first.":
			"Correo o contraseña incorrectos.",
		Kind: "Tipo",
		Title: "Título",
		Details: "Detalles",
		"Your name (optional)": "Su nombre (opcional)",
		"Short summary": "Resumen corto",
		"What happened, and what did you expect?": "¿Qué pasó y qué esperaba?",
		"Tell us what broke or what to change. It will show on the Issues page.":
			"Díganos qué falló o qué cambiar. Aparecerá en la página de Incidencias.",
		"Something broke": "Algo falló",
		"Recommend a change on this page": "Recomendar un cambio en esta página",
		"General recommendation": "Recomendación general",
		"Sent with this report": "Se envía con este reporte",
		"Site-wide (not tied to a page).": "En todo el sitio (no ligado a una página).",
		"So we know who to follow up with": "Para saber a quién contactar",
		"Back to dashboard": "Volver al inicio",
		Submittals: "Submittals",
		Issues: "Incidencias",
		Admin: "Administración",
		Finance: "Finanzas",
		RFIs: "RFIs",
		RFI: "RFI",
		Refresh: "Actualizar",
		"Install desktop app": "Instalar app de escritorio",
		"Download the latest Windows installer. Open the file to install or update.":
			"Descargue el instalador de Windows más reciente. Ábralo para instalar o actualizar.",
		"Downloading…": "Descargando…",
		Filter: "Filtrar",
		Apply: "Aplicar",
		Clear: "Limpiar",
		Chat: "Chat",
		"Open AI assistant": "Abrir asistente de IA",
		"USIS + Grok": "USIS + Grok",
		"Attach a file or link": "Adjuntar archivo o enlace",
		"From this computer": "Desde esta computadora",
		"Paste a link": "Pegar un enlace",
		"Add link": "Agregar enlace",
		"Drop files here": "Suelte los archivos aquí",
		Reset: "Restablecer",
		"Reset view": "Restablecer vista",
		"Reset all": "Restablecer todo",
		Saved: "Guardados",
		Action: "Acción",
		Name: "Nombre",
		Status: "Estado",
		Type: "Tipo",
		City: "Ciudad",
		State: "Estado",
		Company: "Empresa",
		View: "Ver",
		"Loading…": "Cargando…",
		Loading: "Cargando",
		Yes: "Sí",
		No: "No",
		All: "Todos",
		Prev: "Ant.",
		Next: "Sig.",
		Active: "Activo",
		Complete: "Completado",
		Archived: "Archivado",
		Cancelled: "Cancelado",
		"On hold": "En pausa",
		Draft: "Borrador",
		Open: "Abierta",
		Closed: "Cerrada",
		Submitted: "Enviado",
		Overdue: "Vencido",
		Description: "Descripción",
		Number: "Número",
		Subject: "Asunto",
		Question: "Pregunta",
		Location: "Ubicación",
		Reference: "Referencia",
		Attachments: "Adjuntos",
		Assignees: "Asignados",
		Distribution: "Distribución",
		Private: "Privado",
		Trade: "Oficio",
		Vendor: "Proveedor",
		Reviewer: "Revisor",
		Severity: "Severidad",
		Source: "Origen",
		Assignee: "Asignado",
		Project: "Proyecto",
		"Project #": "Proyecto #",
		"Project detail": "Detalle del proyecto",
		"Job info": "Datos del trabajo",
		Schedule: "Programa",
		Tasks: "Tareas",
		Drawings: "Planos",
		Specs: "Especificaciones",
		Takeoff: "Cuantificación",
		Invoicing: "Facturación",
		"Contract admin": "Admin. de contrato",
		"Job costing": "Costos de obra",
		"Construction schedule": "Programa de construcción",
		"Installation dates": "Fechas de instalación",
		Specifications: "Especificaciones",
		Pricing: "Precios",
		Kanban: "Kanban",
		Table: "Tabla",
		"New Issue": "Nueva incidencia",
		"New issue": "Nueva incidencia",
		Issue: "Incidencia",
		"Search issues": "Buscar incidencias",
		"All projects": "Todos los proyectos",
		"All statuses": "Todos los estados",
		"All severities": "Todas las severidades",
		"All trades": "Todos los oficios",
		"All sources": "Todos los orígenes",
		New: "Nueva",
		Triaged: "Clasificada",
		"In Progress": "En progreso",
		"Pending Review": "Pendiente de revisión",
		Resolved: "Resuelta",
		Critical: "Crítica",
		Major: "Mayor",
		Minor: "Menor",
		Drywall: "Tablaroca",
		Paint: "Pintura",
		Flooring: "Pisos",
		Acoustical: "Acústico",
		"Doors & Hardware": "Puertas y herrajes",
		Specialties: "Especialidades",
		General: "General",
		"AI Review": "Revisión IA",
		Punch: "Punch",
		Field: "Campo",
		Manual: "Manual",
		Website: "Sitio web",
		Unassigned: "Sin asignar",
		"No issues": "Sin incidencias",
		"No issues yet.": "Aún no hay incidencias.",
		"Could not load issues": "No se pudieron cargar las incidencias",
		"{n} shown · {c} open critical": "{n} mostradas · {c} críticas abiertas",
		"No description yet.": "Aún no hay descripción.",
		History: "Historial",
		"Create Change Order": "Crear orden de cambio",
		"Create RFI": "Crear RFI",
		"Open in DrawingViewer": "Abrir en visor de planos",
		"Issue created": "Incidencia creada",
		"RFI prefill ready": "RFI lista para completar",
		"Change order prepared from this issue": "Orden de cambio preparada desde esta incidencia",
		"AI review findings added to Issues": "Hallazgos de IA agregados a Incidencias",
		"Status updates from GitHub: work or assign → In Progress, Resolution: comment → Pending Review, reporter confirms → Closed.":
			"Actualizaciones desde GitHub: trabajar o asignar → En progreso, comentario Resolution: → Pendiente de revisión, el reportante confirma → Cerrada.",
		"Construction — Projects": "Construcción — Proyectos",
		"Construction — RFIS": "Construcción — RFIs",
		"Construction — RFI Create": "Construcción — Crear RFI",
		"Construction — Leads": "Construcción — Prospectos",
		"Construction — Estimate": "Construcción — Estimación",
		"Construction — Submitted": "Construcción — Enviados",
		"Reload from API": "Recargar desde API",
		"Filter by #, name, city, or state": "Filtrar por #, nombre, ciudad o estado",
		"Set status": "Cambiar estado",
		"0 selected": "0 seleccionados",
		"{n} selected": "{n} seleccionados",
		"Loading projects from API…": "Cargando proyectos desde la API…",
		"No projects match this filter.": "Ningún proyecto coincide con este filtro.",
		"No projects yet. Add projects in your system, then reload.":
			"Aún no hay proyectos. Agréguelos al sistema y recargue.",
		"No projects yet. Use New project to add one.":
			"Aún no hay proyectos. Use Proyecto nuevo para agregar uno.",
		"New project": "Proyecto nuevo",
		"Name is required.": "El nombre es obligatorio.",
		"Could not create project.": "No se pudo crear el proyecto.",
		"No projects are assigned to your account. Ask an administrator to assign jobs in User admin.":
			"No tiene proyectos asignados. Pida a un administrador que le asigne trabajos.",
		"Showing only projects assigned to you. Contact an administrator if a job is missing.":
			"Solo se muestran los proyectos asignados a usted. Contacte a un administrador si falta un trabajo.",
		"Showing only projects assigned to you (including jobs still in planning). Contact an administrator if a job is missing.":
			"Solo se muestran los proyectos asignados a usted (incluidos los que siguen en planeación). Contacte a un administrador si falta un trabajo.",
		"Saved view": "Vista guardada",
		"Default (all)": "Predeterminada (todas)",
		"Recycle bin": "Papelera",
		"Hide deleted": "Ocultar eliminadas",
		"Show only deleted": "Mostrar solo eliminadas",
		Columns: "Columnas",
		"Save view": "Guardar vista",
		"Subject, question, reference…": "Asunto, pregunta, referencia…",
		"Loading projects…": "Cargando proyectos…",
		"Loading RFIs from API…": "Cargando RFIs desde la API…",
		"Loading RFIs…": "Cargando RFIs…",
		"Closed-Draft": "Cerrada-borrador",
		"Bulk edit…": "Edición masiva…",
		Recycle: "Reciclar",
		Restore: "Restaurar",
		"← Prev": "← Ant.",
		"Next →": "Sig. →",
		"No RFIs match the current filters.": "Ninguna RFI coincide con los filtros.",
		"Select a project to see its RFIs.": "Seleccione un proyecto para ver sus RFIs.",
		"{from}–{to} of {total}": "{from}–{to} de {total}",
		"0 of 0": "0 de 0",
		"Ball in Court": "Pendiente de",
		"RFI Manager": "Gerente de RFI",
		"Received From": "Recibido de",
		"Responsible Contractor": "Contratista responsable",
		"Date Initiated": "Fecha de inicio",
		"Due Date": "Fecha de vencimiento",
		"Closed Date": "Fecha de cierre",
		"Schedule Impact": "Impacto en programa",
		"Cost Impact": "Impacto en costo",
		"Cost $": "Costo $",
		"Cost Code": "Código de costo",
		"Spec Section": "Sección de especificación",
		"Customize columns": "Personalizar columnas",
		"Row height": "Alto de fila",
		Compact: "Compacto",
		Default: "Predeterminado",
		Comfortable: "Cómodo",
		"Reset to default": "Restablecer",
		Scope: "Alcance",
		"My views": "Mis vistas",
		"Project (everyone on this project)": "Proyecto (todos en este proyecto)",
		"Company (everyone)": "Empresa (todos)",
		"Make this my default view": "Usar como mi vista predeterminada",
		"Bulk edit RFIs": "Editar RFIs en lote",
		"My open RFIs": "Mis RFIs abiertas",
		"Create as Draft": "Crear como borrador",
		"Create as Open": "Crear como abierta",
		"Send for review": "Enviar a revisión",
		"Send for Review": "Enviar a revisión",
		"New RFI": "Nueva RFI",
		"Punch List": "Lista de pendientes",
		"New Punch List Item": "Nuevo pendiente",
		"Punch Item Manager": "Gerente del pendiente",
		"Final Approver": "Aprobador final",
		"Select a Person": "Seleccione una persona",
		"Select Type": "Seleccione tipo",
		"Select Priority": "Seleccione prioridad",
		"Select Trade": "Seleccione oficio",
		"Select Schedule Impact": "Seleccione impacto en programa",
		"Select Cost Impact": "Seleccione impacto en costo",
		"Attach Files": "Adjuntar archivos",
		"or Drag & Drop": "o arrastre y suelte",
		"Asterisk indicates required field": "El asterisco indica un campo obligatorio",
		"Save & Create New": "Guardar y crear nuevo",
		"Draft RFI. For draft RFIs, Number and Due Date are both suggested values. Neither will be applied until the RFI is Open.":
			"RFI en borrador. En borradores, el número y la fecha de vencimiento son valores sugeridos. No se aplican hasta que la RFI esté abierta.",
		"Distribution List": "Lista de distribución",
		Specification: "Especificación",
		"RFI Stage": "Etapa de RFI",
		"Response Needed By": "Respuesta necesaria para",
		"Attach Files or Drag & Drop": "Adjunte archivos o arrastre y suelte",
		"Ball In Court": "Pendiente de",
		"Created By": "Creado por",
		"Select a person": "Seleccione una persona",
		"Select a vendor": "Seleccione un proveedor",
		"Select a Specification": "Seleccione una especificación",
		"Select a Location": "Seleccione una ubicación",
		"Select a cost code": "Seleccione un código de costo",
		"Select…": "Seleccione…",
		Notes: "Notas",
		"* required fields": "* campos obligatorios",
		Add: "Agregar",
		"General Information": "Información general",
		Prefix: "Prefijo",
		Auto: "Auto",
		Request: "Solicitud",
		"Leave blank for next sequential.": "Déjelo en blanco para el siguiente consecutivo.",
		"Short descriptive title": "Título descriptivo corto",
		"Make response required": "Hacer respuesta obligatoria",
		"Add assignee": "Agregar asignado",
		"Add to distribution": "Agregar a distribución",
		"Drawing Number": "Número de plano",
		"Project Stage": "Etapa del proyecto",
		"Sub Job": "Subtrabajo",
		Amount: "Monto",
		Days: "Días",
		"Yes (Unknown)": "Sí (desconocido)",
		TBD: "Por definir",
		"N/A": "N/A",
		"General information (background)": "Información general (contexto)",
		"Context that helps interpret the question correctly": "Contexto para interpretar la pregunta",
		"State the question clearly. Reference drawings / specs as needed.":
			"Formule la pregunta con claridad. Cite planos o especificaciones.",
		"Draft with AI (Beta)": "Borrador con IA (Beta)",
		"Generates Subject + Question + Impact fields from a short prompt.":
			"Genera asunto, pregunta e impacto a partir de un texto corto.",
		"Drop files here or click to browse": "Suelte archivos aquí o haga clic para buscar",
		"Attachments are uploaded after the RFI is saved.": "Los adjuntos se suben después de guardar la RFI.",
		"Required to save as Open: Number, Subject, Assignees, Due Date, Question. As Standard you can save as Draft and send for review to your RFI Manager.":
			"Para guardar como Abierta se requieren: Número, Asunto, Asignados, Fecha de vencimiento y Pregunta. En modo estándar puede guardarla como borrador y enviarla a revisión.",
		"Draft RFI with AI": "Borrador de RFI con IA",
		"Describe the field condition or ambiguity in your own words. AI will draft a Subject, Question, and Cost / Schedule Impact suggestion.":
			"Describa la condición de campo o la duda. La IA redactará asunto, pregunta e impacto de costo o programa.",
		"Generate draft": "Generar borrador",
		"Select project…": "Seleccionar proyecto…",
		"Select manager…": "Seleccionar gerente…",
		"Select user…": "Seleccionar usuario…",
		"Choose a project.": "Elija un proyecto.",
		"Type / Status": "Tipo / Estado",
		Address: "Dirección",
		Owner: "Dueño",
		Architect: "Arquitecto",
		Contract: "Contrato",
		Start: "Inicio",
		"Create submittal": "Crear submittal",
		"+ Create submittal": "+ Crear submittal",
		"New Submittal": "Nuevo submittal",
		"Specification": "Especificación",
		"Number & Revision": "Número y revisión",
		"Submittal Type": "Tipo de submittal",
		"Responsible Contractor": "Contratista responsable",
		"Received From": "Recibido de",
		"Final Due Date": "Fecha límite final",
		"Linked Drawings": "Planos vinculados",
		"Distribution List": "Lista de distribución",
		"Ball In Court": "Pendiente de",
		"Visible only to admins, workflow, and distribution list members.":
			"Visible solo para administradores, flujo de trabajo y miembros de la lista de distribución.",
		"Attach Files": "Adjuntar archivos",
		"or Drag & Drop": "o arrastre y suelte",
		"Material Tracking": "Seguimiento de materiales",
		"Material Tracking?": "¿Seguimiento de materiales?",
		"Supply Chain Risk": "Riesgo de cadena de suministro",
		"Manufacturer Location (City, State, Country)": "Ubicación del fabricante (ciudad, estado, país)",
		"Release to contractor": "Liberar al contratista",
		"Comments (Public)": "Comentarios (públicos)",
		"Spec line items": "Partidas de especificación",
		"Submittal Schedule Information": "Información de programa del submittal",
		"Schedule Task": "Tarea del programa",
		"Planned Return Date": "Fecha de devolución planificada",
		"Planned Internal Review Completed Date": "Fecha planificada de revisión interna",
		"Planned Submit By Date": "Fecha planificada de envío",
		"Design Team Review Time": "Tiempo de revisión del equipo de diseño",
		"Internal Review Time": "Tiempo de revisión interna",
		"Delivery Information": "Información de entrega",
		"Anticipated Delivery Date": "Fecha de entrega anticipada",
		"Confirmed Delivery Date": "Fecha de entrega confirmada",
		"Actual Delivery Date": "Fecha de entrega real",
		"Submittal Workflow": "Flujo de trabajo del submittal",
		"Add Step": "Agregar paso",
		"Log submittal": "Registrar submittal",
		"Submittal register": "Registro de submittals",
		"Internal QC gate — no stamp, no buy / receive / install.":
			"Control de calidad interno — sin sello, compra, recepción ni instalación.",
		"Spec section": "Sección de especificación",
		"Needed by": "Se necesita para",
		"In review": "En revisión",
		"Ball in court (name or email)": "Pendiente de (nombre o correo)",
		"Reviewer email": "Correo del revisor",
		"Responsible contractor": "Contratista responsable",
		"Revision label": "Etiqueta de revisión",
		"Review due": "Vence revisión",
		"Submit by": "Enviar antes de",
		"Received date": "Fecha de recepción",
		"Received from": "Recibido de",
		"Shop Drawing": "Plano de taller",
		"Product Information": "Información de producto",
		"Product Manual": "Manual de producto",
		Sample: "Muestra",
		Document: "Documento",
		Other: "Otro",
		"Spec sections": "Secciones de especificación",
		optional: "opcional",
		"Title is enough to create. Check CSI sections only if you want line items.":
			"Con el título basta para crear. Marque secciones CSI solo si quiere partidas.",
		"Find CSI section…": "Buscar sección CSI…",
		"No spec sections on this project yet. You can still create the submittal.":
			"Aún no hay secciones de especificación en este proyecto. Aun así puede crear el submittal.",
		"Selected line items": "Partidas seleccionadas",
		Spec: "Espec.",
		Mfr: "Fab.",
		Model: "Modelo",
		"Product data submittals auto-link ASI / Bobrick technical data when manufacturer name matches.":
			"Los submittals de datos de producto enlazan automáticamente fichas ASI / Bobrick si coincide el fabricante.",
		"No submittals": "Sin submittals",
		"No submittals.": "Sin submittals.",
		"Create a package to start internal QC.": "Cree un paquete para iniciar el control de calidad.",
		"Open RFI Log": "Abrir bitácora de RFIs",
		"+ Create RFI": "+ Crear RFI",
		"Subject, ball in court…": "Asunto, pendiente de…",
		"Title, spec section, contractor…": "Título, sección, contratista…",
		"Loading job information…": "Cargando datos del trabajo…",
		"Expected install date": "Fecha de instalación prevista",
		"Shipping address": "Dirección de envío",
		"Ship to": "Enviar a",
		"Office locations": "Ubicaciones de oficina",
		"Company settings": "Configuración de la empresa",
		"Open pricing workspace": "Abrir espacio de precios",
		"Open full page": "Abrir página completa",
		"+ Upload / add": "+ Subir / agregar",
		Discipline: "Disciplina",
		Set: "Juego",
		"Sheet #, title, set, discipline…": "Hoja #, título, juego, disciplina…",
		"All status": "Todos los estados",
		"Not started": "No iniciado",
		Ongoing: "En curso",
		Completed: "Completado",
		"Assigned contains": "Asignado contiene",
		"Name, email, or crew": "Nombre, correo o cuadrilla",
		Download: "Descargar",
		"+ Add task": "+ Agregar tarea",
		"+ Add window": "+ Agregar ventana",
		"Area / scope": "Área / alcance",
		End: "Fin",
		Assigned: "Asignado",
		"Crew (optional)": "Cuadrilla (opcional)",
		"Purchase orders": "Órdenes de compra",
		Subcontracts: "Subcontratos",
		RFPs: "RFPs",
		"Material orders": "Pedidos de material",
		"New PO": "Nueva OC",
		"+ New PO": "+ Nueva OC",
		"+ New subcontract": "+ Nuevo subcontrato",
		"New RFP draft": "Nuevo borrador de RFP",
		"Full RFP workspace": "Espacio completo de RFP",
		"Contract admin hub": "Centro de admin. de contrato",
		Index: "Índice",
		"Add lead": "Agregar prospecto",
		"Sync BC": "Sincronizar BC",
		"Reconnect BC": "Reconectar BC",
		"Will Bid": "Va a cotizar",
		"Will Not Bid": "No va a cotizar",
		Undecided: "Indeciso",
		"Trade invited": "Oficio invitado",
		Dist: "Dist.",
		"Bid due date": "Fecha de cotización",
		"Lead (Building Connected)": "Prospecto (Building Connected)",
		"Filter table (lead, trade, company, city, state, distance, bid due)":
			"Filtrar tabla (prospecto, oficio, empresa, ciudad, estado, distancia, fecha)",
		"Saved filters": "Filtros guardados",
		"Save filter": "Guardar filtro",
		"Filter name": "Nombre del filtro",
		"Set as my default view": "Usar como mi vista predeterminada",
		"No saved filters yet": "Aún no hay filtros guardados",
		"No saved filters yet. Set criteria, then Save filter.":
			"Aún no hay filtros guardados. Defina criterios y luego guarde el filtro.",
		"Clear all": "Limpiar todo",
		"Sort & Filter": "Ordenar y filtrar",
		"Distance from office": "Distancia desde la oficina",
		"Any distance": "Cualquier distancia",
		"Within 25 miles": "Dentro de 25 millas",
		"Within 50 miles": "Dentro de 50 millas",
		"Within 100 miles": "Dentro de 100 millas",
		"Within 150 miles": "Dentro de 150 millas",
		"Within 250 miles": "Dentro de 250 millas",
		"Custom miles…": "Millas personalizadas…",
		"Work performed": "Trabajo realizado",
		Companies: "Empresas",
		Sector: "Sector",
		Commercial: "Comercial",
		Government: "Gobierno",
		"Pipeline stage": "Etapa del embudo",
		"New Lead": "Prospecto nuevo",
		Invited: "Invitado",
		Estimating: "Estimando",
		Awarded: "Adjudicado",
		Lost: "Perdido",
		"Date filters": "Filtros de fecha",
		"Expected start date": "Fecha de inicio prevista",
		"View all date filters": "Ver todos los filtros de fecha",
		"Last activity date": "Fecha de última actividad",
		Value: "Valor",
		"Owner / estimator": "Dueño / estimador",
		"Save office": "Guardar oficina",
		"job name, GC, city, bid #": "obra, GC, ciudad, # de cotización",
		"Loading leads from API…": "Cargando prospectos desde la API…",
		"No current Bid Board leads. The list matches Undecided parents/standalones that are assigned and still due.":
			"No hay prospectos actuales en Bid Board. La lista muestra indecisos asignados que aún tienen fecha.",
		"No rows match your filter. Clear the search box to see all loaded leads (or reload if the list is empty).":
			"Ninguna fila coincide. Limpie la búsqueda para ver los prospectos cargados.",
		"No criteria": "Sin criterios",
		"Filter name is required": "Se requiere un nombre de filtro",
		"Filter updated": "Filtro actualizado",
		"Filter saved": "Filtro guardado",
		Ceilings: "Cielos",
		Trim: "Molduras",
		Multi: "Múltiple",
		"Rubber-stamp suspect": "Posible sello automático",
		Rev: "Rev.",
		"Project ID": "ID de proyecto",
	};

	function supported(code) {
		return code === "es_ES" || code === "en_GB";
	}

	function readCookie() {
		var parts = ("; " + document.cookie).split("; " + COOKIE + "=");
		if (parts.length < 2) return "";
		return parts.pop().split(";").shift() || "";
	}

	function writeCookie(lang) {
		document.cookie = COOKIE + "=" + lang + ";path=/;max-age=31536000;SameSite=Lax";
	}

	function getLang() {
		try {
			var stored = global.localStorage.getItem(KEY);
			if (supported(stored)) return stored;
		} catch (e) {}
		var cookie = readCookie();
		if (supported(cookie)) return cookie;
		return "en_GB";
	}

	function setLang(code) {
		var lang = supported(code) ? code : "en_GB";
		try {
			global.localStorage.setItem(KEY, lang);
		} catch (e) {}
		writeCookie(lang);
		if (document.body) document.body.setAttribute("data-language", lang);
		document.documentElement.setAttribute("lang", lang === "es_ES" ? "es" : "en");
		return lang;
	}

	function tr(key, lang) {
		lang = lang || getLang();
		if (!key) return "";
		if (lang !== "es_ES") return key;
		return ES[key] != null ? ES[key] : key;
	}

	function remember(el, attr, value) {
		var flag = "data-i18n-src" + (attr ? "-" + attr : "");
		if (!el.getAttribute(flag) && value) el.setAttribute(flag, value);
		return el.getAttribute(flag) || value || "";
	}

	function applyText(el, lang) {
		var explicit = el.getAttribute("data-i18n");
		// Never flatten unmarked wrappers: .auth-form p often contains <a href> links.
		if (el.children && el.children.length && !explicit) return;
		var key = explicit || remember(el, "", (el.textContent || "").trim());
		if (!key) return;
		remember(el, "", key);
		var translated = tr(el.getAttribute("data-i18n-src") || key, lang);
		if (el.children && el.children.length) {
			for (var i = 0; i < el.childNodes.length; i++) {
				var n = el.childNodes[i];
				if (n.nodeType === 3 && n.textContent.trim()) {
					n.textContent = n.textContent.replace(n.textContent.trim(), translated);
					return;
				}
			}
			return;
		}
		el.textContent = translated;
	}

	function applyPlaceholder(el, lang) {
		var key = el.getAttribute("data-i18n-placeholder") || remember(el, "placeholder", el.getAttribute("placeholder") || "");
		if (!key) return;
		el.setAttribute("placeholder", tr(key, lang));
	}

	function applyTitle(el, lang) {
		var key = el.getAttribute("data-i18n-title") || remember(el, "title", el.getAttribute("title") || "");
		if (!key) return;
		el.setAttribute("title", tr(key, lang));
	}

	function applyAria(el, lang) {
		var key = el.getAttribute("data-i18n-aria") || remember(el, "aria", el.getAttribute("aria-label") || "");
		if (!key) return;
		el.setAttribute("aria-label", tr(key, lang));
	}

	function apply(lang) {
		if (applying) return setLang(lang || getLang());
		applying = true;
		lang = setLang(lang || getLang());
		try {
			document.querySelectorAll("[data-i18n]").forEach(function (el) {
				applyText(el, lang);
			});
			document.querySelectorAll(".deznav .nav-text, .deznav .menu-title").forEach(function (el) {
				applyText(el, lang);
			});
			document.querySelectorAll(".auth-form h3, .auth-form p, .auth-form label, .auth-form .btn, .auth-form .form-check-label, .auth-form a.btn-link, .auth-form span.small").forEach(function (el) {
				if (el.children && el.children.length) return;
				applyText(el, lang);
			});
			document.querySelectorAll("[data-i18n-placeholder], .header-search input[placeholder]").forEach(function (el) {
				applyPlaceholder(el, lang);
			});
			document.querySelectorAll("[data-i18n-title], .usis-report-problem-btn[title]").forEach(function (el) {
				applyTitle(el, lang);
			});
			document.querySelectorAll("[data-i18n-aria], .usis-report-problem-btn[aria-label]").forEach(function (el) {
				applyAria(el, lang);
			});
			document.querySelectorAll(".header-profile-dropdown .dropdown-item span, #usis-report-problem-modal .modal-title, #usis-report-problem-modal .btn, #usis-report-problem-modal .form-label, #usis-report-problem-modal .text-muted, .notification_dropdown .text-muted, .notification_dropdown a.d-block").forEach(function (el) {
				if (el.closest && el.closest("[data-i18n]")) return;
				applyText(el, lang);
			});
			var switcher = document.getElementById("langSwitcher");
			if (switcher && switcher.value !== lang) {
				switcher.value = lang;
				if (global.jQuery && global.jQuery.fn.selectpicker) {
					global.jQuery(switcher).selectpicker("val", lang);
				}
			}
			document.querySelectorAll("[data-usis-set-lang]").forEach(function (btn) {
				var on = btn.getAttribute("data-usis-set-lang") === lang;
				btn.classList.toggle("active", on);
				btn.setAttribute("aria-pressed", on ? "true" : "false");
				if (btn.classList.contains("btn")) {
					btn.classList.toggle("btn-primary", on);
					btn.classList.toggle("btn-outline-secondary", !on);
				}
			});
		} finally {
			applying = false;
		}
		try {
			document.dispatchEvent(new CustomEvent("usis:languagechange", { detail: { lang: lang } }));
		} catch (e) {}
		return lang;
	}

	function profileMenuItem() {
		var menu = document.querySelector(".header-profile-dropdown .dropdown-menu");
		if (!menu) return null;
		var links = menu.querySelectorAll("a.dropdown-item[href]");
		for (var i = 0; i < links.length; i++) {
			var href = (links[i].getAttribute("href") || "").split("?")[0];
			if (href.indexOf("usis-profile.html") !== -1) return links[i].closest("li");
		}
		return null;
	}

	function ensureProfileLangMenu() {
		var menu = document.querySelector(".header-profile-dropdown .dropdown-menu");
		if (!menu || menu.querySelector("[data-usis-profile-lang]")) return;
		var li = document.createElement("li");
		li.setAttribute("data-usis-profile-lang", "1");
		li.innerHTML =
			'<div class="px-3 py-2">' +
			'<div class="small text-muted mb-1" data-i18n="Language">Language</div>' +
			'<div class="btn-group btn-group-sm w-100" role="group" aria-label="Language">' +
			'<button type="button" class="btn btn-outline-secondary" data-usis-set-lang="en_GB">English</button>' +
			'<button type="button" class="btn btn-outline-secondary" data-usis-set-lang="es_ES">Español</button>' +
			"</div></div>";
		var after = profileMenuItem();
		if (after && after.parentNode) {
			if (after.nextSibling) after.parentNode.insertBefore(li, after.nextSibling);
			else after.parentNode.appendChild(li);
			return;
		}
		var firstDivider = menu.querySelector(".dropdown-divider");
		if (firstDivider && firstDivider.closest("li")) {
			var wrap = firstDivider.closest("li");
			if (wrap.nextSibling) menu.insertBefore(li, wrap.nextSibling);
			else menu.appendChild(li);
			return;
		}
		menu.appendChild(li);
	}

	function bind() {
		var switcher = document.getElementById("langSwitcher");
		if (switcher && !switcher.getAttribute("data-usis-i18n-bound")) {
			switcher.setAttribute("data-usis-i18n-bound", "1");
			switcher.addEventListener("change", function () {
				var next = switcher.value === "es_ES" ? "es_ES" : "en_GB";
				apply(next);
			});
		}
		document.querySelectorAll("[data-usis-set-lang]").forEach(function (btn) {
			if (btn.getAttribute("data-usis-i18n-bound")) return;
			btn.setAttribute("data-usis-i18n-bound", "1");
			btn.addEventListener("click", function () {
				apply(btn.getAttribute("data-usis-set-lang"));
			});
		});
	}

	function init() {
		ensureProfileLangMenu();
		bind();
		apply(getLang());
	}

	global.USISI18n = {
		getLang: getLang,
		setLang: setLang,
		apply: apply,
		tr: tr,
		init: init,
	};

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})(typeof window !== "undefined" ? window : this);
