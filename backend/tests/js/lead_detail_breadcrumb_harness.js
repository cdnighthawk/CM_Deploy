"use strict";

const fs = require("fs");
const vm = require("vm");
const assert = require("assert");

const jsPath = process.argv[2];
if (!jsPath) {
  console.error("usage: node lead_detail_breadcrumb_harness.js <usis-project-context.js>");
  process.exit(2);
}
const code = fs.readFileSync(jsPath, "utf8");

function el(tag, attrs) {
  const node = {
    tagName: String(tag || "div").toUpperCase(),
    id: (attrs && attrs.id) || "",
    className: (attrs && attrs.className) || "",
    href: (attrs && attrs.href) || "",
    textContent: (attrs && attrs.textContent) || "",
    children: [],
    attrs: Object.assign({}, attrs || {}),
    classList: {
      add(c) {
        const parts = node.className.split(/\s+/).filter(Boolean);
        if (!parts.includes(c)) parts.push(c);
        node.className = parts.join(" ");
      },
      remove(c) {
        node.className = node.className
          .split(/\s+/)
          .filter((x) => x && x !== c)
          .join(" ");
      },
      contains(c) {
        return node.className.split(/\s+/).includes(c);
      },
    },
    setAttribute(k, v) {
      node.attrs[k] = v;
      if (k === "href") node.href = v;
      if (k === "id") node.id = v;
      if (k === "class") node.className = v;
    },
    getAttribute(k) {
      if (k === "href") return node.href;
      if (k === "id") return node.id;
      return node.attrs[k];
    },
    removeAttribute(k) {
      delete node.attrs[k];
    },
    appendChild(child) {
      node.children.push(child);
      child.parentNode = node;
      return child;
    },
    querySelector(sel) {
      if (sel === "a") {
        if (node.tagName === "A") return node;
        return node.children.find((c) => c.tagName === "A") || null;
      }
      if (sel === ".breadcrumb-item.active") {
        return node.children.find((c) => /\bactive\b/.test(c.className)) || null;
      }
      return null;
    },
    querySelectorAll() {
      return [];
    },
    closest() {
      return null;
    },
  };
  return node;
}

function runCase(opts) {
  const store = Object.assign({}, opts.session || {});
  const projectsLi = el("li", {
    id: "usis-projects-crumb",
    className: "breadcrumb-item d-none",
  });
  const projectsA = el("a", {
    href: "construction/projects.html",
    "data-i18n": "Active projects",
    textContent: "Active projects",
  });
  projectsLi.appendChild(projectsA);
  const projectLi = el("li", {
    id: "usis-project-crumb",
    className: "breadcrumb-item d-none",
  });
  const projectA = el("a", {
    id: "usis-project-crumb-link",
    href: "construction/projects.html",
  });
  projectLi.appendChild(projectA);
  const active = el("li", { className: "breadcrumb-item active" });
  const ol = el("ol", { className: "breadcrumb" });
  ol.children = [projectsLi, projectLi, active];
  ol.querySelector = function (sel) {
    if (sel === ".breadcrumb-item.active") return active;
    return null;
  };

  const byId = {
    "usis-projects-crumb": projectsLi,
    "usis-project-crumb": projectLi,
    "usis-project-crumb-link": projectA,
  };

  const body = el("body", {});
  body.setAttribute = function (k, v) {
    body.attrs[k] = v;
  };
  body.removeAttribute = function (k) {
    delete body.attrs[k];
  };
  body.getAttribute = function (k) {
    return body.attrs[k] || null;
  };

  const document = {
    readyState: "complete",
    referrer: opts.referrer || "",
    body,
    querySelector(sel) {
      if (sel === ".page-title .breadcrumb") return ol;
      if (sel === ".usis-mobile-bottomnav") return null;
      return null;
    },
    querySelectorAll() {
      return [];
    },
    getElementById(id) {
      return byId[id] || null;
    },
    createElement(tag) {
      return el(tag, {});
    },
    addEventListener() {},
  };

  const location = {
    pathname: opts.pathname,
    search: opts.search || "",
    href: "https://www.usiscm.com" + opts.pathname + (opts.search || ""),
  };

  const sandbox = {
    window: {},
    document,
    location,
    URL,
    URLSearchParams,
    fetch: function () {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: function () {
          return Promise.resolve({
            item: { id: "proj-1", number: "", name: "YMCA Fullerton Phase 2" },
          });
        },
      });
    },
    sessionStorage: {
      getItem(k) {
        return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null;
      },
      setItem(k, v) {
        store[k] = String(v);
      },
      removeItem(k) {
        delete store[k];
      },
    },
    console,
  };
  sandbox.window = sandbox;
  sandbox.global = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(code, sandbox, { filename: "usis-project-context.js" });

  if (opts.setProjectId) {
    sandbox.USISProjectContext.setProjectId(opts.setProjectId);
  }

  function snapshot() {
    return {
      listLabel: projectsA.textContent,
      listHref: projectsA.href,
      listHidden: projectsLi.classList.contains("d-none"),
      jobLabel: projectA.textContent,
      jobHref: projectA.href,
      jobHidden: projectLi.classList.contains("d-none"),
    };
  }

  function waitTicks(n) {
    if (n <= 0) return Promise.resolve(snapshot());
    return new Promise(function (resolve) {
      setImmediate(resolve);
    }).then(function () {
      return waitTicks(n - 1);
    });
  }

  return waitTicks(8);
}

Promise.all([
  runCase({
    pathname: "/construction/lead-detail.html",
    search: "?id=6aa86fe841e52c819ba281f5",
    referrer: "https://www.usiscm.com/construction/leads.html",
    setProjectId: "proj-1",
  }).then(function (got) {
    assert.strictEqual(got.listLabel, "Leads", JSON.stringify(got));
    assert.strictEqual(got.listHref, "construction/leads.html");
    assert.strictEqual(got.listHidden, false);
    assert.strictEqual(got.jobLabel, "YMCA Fullerton Phase 2", JSON.stringify(got));
    assert.ok(got.jobHref.indexOf("lead-detail.html") !== -1, got.jobHref);
    assert.ok(got.jobHref.indexOf("project-detail.html") === -1, got.jobHref);
    assert.strictEqual(got.jobHidden, false);
  }),
  runCase({
    pathname: "/construction/lead-detail.html",
    search: "?id=6aa86fe841e52c819ba281f5&from=projects",
    referrer: "https://www.usiscm.com/construction/project-detail.html?id=abc",
    setProjectId: "proj-1",
  }).then(function (got) {
    assert.strictEqual(got.listLabel, "Active projects", JSON.stringify(got));
    assert.strictEqual(got.listHref, "construction/projects.html");
    assert.strictEqual(got.listHidden, false);
    assert.ok(got.jobHref.indexOf("project-detail.html") !== -1, got.jobHref);
  }),
  runCase({
    pathname: "/construction/project-detail.html",
    search: "?id=proj-1",
    setProjectId: "proj-1",
  }).then(function (got) {
    assert.strictEqual(got.listLabel, "Active projects", JSON.stringify(got));
    assert.strictEqual(got.listHref, "construction/projects.html");
    assert.ok(got.jobHref.indexOf("project-detail.html") !== -1, got.jobHref);
  }),
  runCase({
    pathname: "/construction/lead-detail.html",
    search: "?id=6aa86fe841e52c819ba281f5",
    referrer: "",
  }).then(function (got) {
    assert.strictEqual(got.listLabel, "Leads", JSON.stringify(got));
    assert.strictEqual(got.listHref, "construction/leads.html");
    assert.strictEqual(got.listHidden, false);
  }),
])
  .then(function () {
    console.log("ok");
  })
  .catch(function (err) {
    console.error(err && err.stack ? err.stack : err);
    process.exit(1);
  });
