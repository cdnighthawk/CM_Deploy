#!/usr/bin/env node
/**
 * Sanity check: verify every data-usis-show-tab in project-detail.html
 * maps to the parent group it sits in, matching the TAB_TO_PARENT map
 * in project-detail-tools-nav.js
 */
"use strict";

const fs = require("fs");
const path = require("path");

// Read the HTML and JS files
const htmlPath = path.join(__dirname, "W3CRM-v3.0-13_September_2025/gulp/src/construction/project-detail.html");
const jsPath = path.join(__dirname, "W3CRM-v3.0-13_September_2025/gulp/src/assets/js/project-detail-tools-nav.js");

const htmlContent = fs.readFileSync(htmlPath, "utf8");
const jsContent = fs.readFileSync(jsPath, "utf8");

// Extract TAB_TO_PARENT mapping from JS
const tabToParentMatch = jsContent.match(/var TAB_TO_PARENT = \{([^}]+)\}/s);
if (!tabToParentMatch) {
	console.error("ERROR: Could not find TAB_TO_PARENT in JS file");
	process.exit(1);
}

const tabToParent = {};
const entries = tabToParentMatch[1].matchAll(/"([^"]+)":\s*"([^"]+)"/g);
for (const match of entries) {
	tabToParent[match[1]] = match[2];
}

console.log("TAB_TO_PARENT from JS:");
console.log(tabToParent);
console.log("");

// Extract parent groups from HTML
const groupRegex = /<div[^>]+class="usis-project-subtools__group"[^>]+data-usis-parent="([^"]+)"[^>]*>([\s\S]*?)<\/div>/g;
const htmlGroups = {};
let groupMatch;

while ((groupMatch = groupRegex.exec(htmlContent)) !== null) {
	const parent = groupMatch[1];
	const groupContent = groupMatch[2];
	
	// Extract all data-usis-show-tab values in this group
	const tabRegex = /data-usis-show-tab="([^"]+)"/g;
	const tabs = [];
	let tabMatch;
	
	while ((tabMatch = tabRegex.exec(groupContent)) !== null) {
		tabs.push(tabMatch[1]);
	}
	
	if (!htmlGroups[parent]) {
		htmlGroups[parent] = [];
	}
	htmlGroups[parent].push(...tabs);
}

console.log("HTML groups:");
for (const [parent, tabs] of Object.entries(htmlGroups)) {
	console.log(`  ${parent}: ${tabs.join(", ")}`);
}
console.log("");

// Verify mapping
let errors = 0;
console.log("Verification:");

for (const [tab, expectedParent] of Object.entries(tabToParent)) {
	let foundInParent = null;
	
	for (const [parent, tabs] of Object.entries(htmlGroups)) {
		if (tabs.includes(tab)) {
			foundInParent = parent;
			break;
		}
	}
	
	if (!foundInParent) {
		console.log(`  ✗ ${tab}: in TAB_TO_PARENT → ${expectedParent}, but NOT FOUND in HTML`);
		errors++;
	} else if (foundInParent !== expectedParent) {
		console.log(`  ✗ ${tab}: in TAB_TO_PARENT → ${expectedParent}, but in HTML → ${foundInParent}`);
		errors++;
	} else {
		console.log(`  ✓ ${tab}: ${expectedParent}`);
	}
}

console.log("");
if (errors > 0) {
	console.log(`FAILED: ${errors} mismatches found`);
	process.exit(1);
} else {
	console.log("SUCCESS: All tabs map correctly to their parent groups");
	process.exit(0);
}
