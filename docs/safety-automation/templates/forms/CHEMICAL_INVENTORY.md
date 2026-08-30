# PROJECT CHEMICAL INVENTORY

**{{company.shortName}}** · {{project.name}}  
Generated {{doc.generatedAt}}  
SDS location: company portal and/or job binder.

| Product | Manufacturer | Use location | SDS on file |
|---|---|---|---|
{{#each chemicals}}
| {{productName}} | {{manufacturer}} | {{useLocation}} | {{sdsUrl}} |
{{else}}
| _No chemicals entered yet. Add products before they are used._ | | | |
{{/each}}

Added after mobilization must be entered in the project record and this page regenerated.
