/**
 * Local preview generator. Website should reimplement with the same tokens.
 * Usage: node engine/generate.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function loadJson(rel) {
  return JSON.parse(fs.readFileSync(path.join(root, rel), "utf8"));
}

function formatAddress(a = {}) {
  return [a.line1, a.line2, [a.city, a.state].filter(Boolean).join(", "), a.zip]
    .filter(Boolean)
    .join(", ");
}

function missingFields(project) {
  const miss = [];
  if (!project.superintendent?.name) miss.push("superintendent.name");
  if (!project.superintendent?.phone) miss.push("superintendent.phone");
  if (!project.emergency?.musterPoint) miss.push("emergency.musterPoint");
  if (!project.emergency?.hospital?.name) miss.push("emergency.hospital.name");
  if (!project.emergency?.hospital?.phone) miss.push("emergency.hospital.phone");
  if (!project.emergency?.whoCalls911) miss.push("emergency.whoCalls911");
  if (!project.emergency?.directionsFor911) miss.push("emergency.directions911");
  if (!project.address?.line1 && !project.address?.city) miss.push("project.address");
  return miss;
}

function ctx(company, project) {
  const miss = missingFields(project);
  return {
    company: {
      legalName: company.legalName,
      dba: company.dba,
      shortName: company.shortName,
      displayName: `${company.legalName} dba ${company.dba}`,
      admin: company.iippAdministrator,
      phone: company.phones,
      afterHoursPhone: company.afterHoursPhone,
      address: { block: formatAddress(company.addresses?.primary) },
      languages: (company.languages || []).join(" and "),
    },
    project: {
      name: project.projectName,
      number: project.projectNumber,
      client: project.clientName || "—",
      gc: project.gcName || "—",
      role: project.roleOnSite,
      address: { block: formatAddress(project.address), city: project.address?.city },
      accessNotes: project.accessNotes || "—",
      startDate: project.startDate || "—",
      endDate: project.endDate || "—",
      crewSize: project.crewSizeTypical ?? "—",
      languages: (project.languagesOnSite || []).join(", "),
      superintendent: project.superintendent || {},
      pm: project.projectManager || {},
      ppeList: (project.ppeRequired || []).map((p) => `- ${p}`).join("\n"),
      gcRules: project.gcRulesStricter || "—",
      notes: project.notes || "",
    },
    emergency: {
      muster: project.emergency?.musterPoint,
      muster2: project.emergency?.secondaryMuster || "—",
      who911: project.emergency?.whoCalls911,
      whoCalOsha: project.emergency?.whoCallsCalOsha || company.iippAdministrator?.name,
      hospital: project.emergency?.hospital || {},
      clinic: project.emergency?.clinic || {},
      fire: project.emergency?.fireDept || "911",
      police: project.emergency?.police || "911",
      calOsha: project.emergency?.calOshaDistrictOffice || {},
      cellOk: project.emergency?.cellCoverageReliable ? "Yes" : "No — use radio or runner",
      radio: project.emergency?.radioChannel || "—",
      directions911: project.emergency?.directionsFor911,
    },
    climate: {
      outdoor: project.climate?.outdoorWork ? "Yes" : "No",
      indoor: project.climate?.indoorWork ? "Yes" : "No",
      elevation: project.climate?.elevationFt ?? "—",
      heatRisk: project.climate?.heatRisk || "—",
      cold: project.climate?.coldIceSnow ? "Yes" : "No",
      smoke: project.climate?.wildfireSmokePossible ? "Yes" : "No",
      notes: project.climate?.notes || "",
    },
    scope: project.scope || {},
    cp: project.competentPersons || {},
    chemicals: project.chemicals || [],
    calOsha: {
      "342Text": company.calOsha?.seriousInjuryRule,
    },
    doc: {
      version: "0.1.0-draft",
      generatedAt: new Date().toISOString(),
      effectiveDate: project.startDate || new Date().toISOString().slice(0, 10),
      nextReview: "12 months from effective date (heat: each April)",
      missingFields: miss.join(", "),
    },
  };
}

function get(obj, path) {
  return path.split(".").reduce((o, k) => (o == null ? o : o[k]), obj);
}

function render(template, data) {
  let out = template;
  out = out.replace(/\{\{#if doc\.missingFields\}\}([\s\S]*?)\{\{\/if\}\}/g, (_, inner) =>
    data.doc.missingFields ? inner : ""
  );
  out = out.replace(/\{\{#if ([a-zA-Z0-9_.]+)\}\}([\s\S]*?)\{\{\/if\}\}/g, (_, key, inner) => {
    const v = get(data, key);
    const truthy = v === true || v === "Yes" || (typeof v === "string" && v.length > 0 && v !== "—" && key.startsWith("scope.") === false && key.startsWith("climate.") === false)
      ? Boolean(v)
      : Boolean(v);
    if (key.startsWith("scope.") || key.startsWith("climate.")) {
      return v === true || v === "Yes" ? inner : "";
    }
    return v ? inner : "";
  });
  out = out.replace(/\{\{#each chemicals\}\}([\s\S]*?)\{\{else\}\}([\s\S]*?)\{\{\/each\}\}/g, (_, row, empty) => {
    if (!data.chemicals?.length) return empty;
    return data.chemicals
      .map((c) =>
        row
          .replace(/\{\{productName\}\}/g, c.productName || "")
          .replace(/\{\{manufacturer\}\}/g, c.manufacturer || "")
          .replace(/\{\{useLocation\}\}/g, c.useLocation || "")
          .replace(/\{\{sdsUrl\}\}/g, c.sdsUrl || "")
      )
      .join("");
  });
  out = out.replace(/\{\{([^}#/]+)\}\}/g, (_, key) => {
    const v = get(data, key.trim());
    if (v == null || v === "") return "—";
    if (typeof v === "object") return JSON.stringify(v);
    return String(v);
  });
  return out;
}

const company = loadJson("data/company.seed.json");
const project = loadJson("data/project.mammoth.sample.json");
const data = ctx(company, project);

const files = [
  "templates/company/IIPP.md",
  "templates/company/WVPP.md",
  "templates/company/HEAT_ILLNESS_PREVENTION.md",
  "templates/company/HAZCOM.md",
  "templates/company/CODE_OF_SAFE_PRACTICES.md",
  "templates/project/SITE_CARD.md",
  "templates/project/SSSP.md",
  "templates/project/ORIENTATION.md",
  "templates/forms/DAILY_PTP.md",
  "templates/forms/INSPECTION.md",
  "templates/forms/TOOLBOX.md",
  "templates/forms/INCIDENT.md",
  "templates/forms/CHEMICAL_INVENTORY.md",
];

const outDir = path.join(root, "sample", "mammoth-preview");
fs.mkdirSync(outDir, { recursive: true });
for (const rel of files) {
  const rendered = render(fs.readFileSync(path.join(root, rel), "utf8"), data);
  const base = path.basename(rel);
  fs.writeFileSync(path.join(outDir, base), rendered);
}
fs.writeFileSync(path.join(outDir, "_context.json"), JSON.stringify(data, null, 2));
console.log(`Wrote ${files.length} previews to sample/mammoth-preview`);
console.log("Missing fields:", data.doc.missingFields || "(none)");
