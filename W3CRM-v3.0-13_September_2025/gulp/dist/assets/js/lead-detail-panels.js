/**
 * Lead detail — Drawings, Specs, RFI tabs (project-linked).
 */
(function () {
	"use strict";

	if (typeof window.USISProjectDocPanels === "undefined") return;

	window.USISProjectDocPanels.init({
		event: "usis-lead-loaded",
		returnUrl: true,
		ensureProjectFromLead: true,
		allowDrawingsWithoutProject: true,
		fromPage: "lead",
		getProjectId: function (it) {
			return it && (it.drawing_project_id || it.project_id);
		},
		panes: {
			drawings: "lead-pane-drawings",
			specs: "lead-pane-specs",
			rfi: "lead-pane-rfi",
		},
		ids: {
			drawingsNoProject: "usis-lead-drawings-no-project",
			drawingsTools: "usis-lead-drawings-tools",
			openViewer: "usis-lead-open-viewer",
			drawingUploadOpen: "usis-lead-drawing-upload-open",
			gridDrawings: "usis-lead-grid-drawings",
			searchDrawings: "usis-lead-search-drawings",
			filterDrawingDiscipline: "usis-lead-filter-drawing-discipline",
			filterDrawingSet: "usis-lead-filter-drawing-set",
			specsNoProject: "usis-lead-specs-no-project",
			specsRoot: "usis-lead-specs-root",
			specsOpenFull: "usis-lead-specs-open-full",
			rfiNoProject: "usis-lead-rfi-no-project",
			rfiTools: "usis-lead-rfi-tools",
			rfiOpenLog: "usis-lead-rfi-open-log",
			rfiOpenCreate: "usis-lead-rfi-open-create",
			searchRfis: "usis-lead-search-rfis",
			filterRfiStatus: "usis-lead-filter-rfi-status",
			tbodyRfis: "usis-lead-tbody-rfis",
			drawingUploadSubmit: "usis-lead-drawing-upload-submit",
			drawingUploadErr: "usis-lead-drawing-upload-err",
			drawingFile: "usis-lead-drawing-file",
			drawingDiscipline: "usis-lead-drawing-discipline",
			drawingSet: "usis-lead-drawing-set",
			modalDrawingCreate: "usis-lead-modal-drawing-create",
		},
	});
})();
