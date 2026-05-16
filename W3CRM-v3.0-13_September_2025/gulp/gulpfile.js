// Gulp JS plugins and modules
const http = require("http");
const { URL } = require("url");
const { src, dest, watch, parallel, series } = require("gulp");

const FLASK_API_TARGET = process.env.USIS_FLASK_PROXY || "http://127.0.0.1:5000";

/** Proxy /api, /auth, /healthz to Flask so session cookies work from :3000 pages. */
function flaskApiProxyMiddleware(req, res, next) {
  const raw = req.url || "";
  const pathOnly = raw.split("?")[0];
  if (
    !pathOnly.startsWith("/api/") &&
    !pathOnly.startsWith("/auth/") &&
    pathOnly !== "/healthz"
  ) {
    return next();
  }
  let target;
  try {
    target = new URL(raw, FLASK_API_TARGET);
  } catch (e) {
    res.writeHead(400, { "Content-Type": "text/plain" });
    res.end("Bad proxy URL");
    return;
  }
  const headers = Object.assign({}, req.headers, { host: target.host });
  const proxyReq = http.request(
    {
      hostname: target.hostname,
      port: target.port || (target.protocol === "https:" ? 443 : 80),
      path: target.pathname + target.search,
      method: req.method,
      headers: headers,
    },
    (proxyRes) => {
      res.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
      proxyRes.pipe(res);
    }
  );
  proxyReq.on("error", (err) => {
    res.writeHead(502, { "Content-Type": "text/plain" });
    res.end("Flask API unreachable at " + FLASK_API_TARGET + " (" + err.message + ")");
  });
  if (req.method === "GET" || req.method === "HEAD") {
    proxyReq.end();
  } else {
    req.pipe(proxyReq);
  }
}

// Rename file names like main.scss > style.css
const rename = require("gulp-rename");

// Live reload and preview server
const browserSync = require("browser-sync").create();

// HTML partial includes using @@include()
const fileinclude = require("gulp-file-include");

// Read and combine CSS/JS build blocks in HTML
const useref = require("gulp-useref");

// Use conditionally for *.css or *.js
const gulpIf = require("gulp-if");

// Minify JS
const uglify = require("gulp-uglify");

// Copy node_modules dependencies
const npmFiles = require("gulp-npm-files");

// PostCSS plugins (autoprefixer, cssnano)
const postcss = require("gulp-postcss");

// Convert LTR CSS to RTL (right-to-left)
const rtlcss = require("gulp-rtlcss");

// Minify CSS using PostCSS
const cssnano = require("cssnano");

// Replace strings in files
const replace = require("gulp-replace");

// Delete files/folders
const del = require("del");

// Vendor prefixer for CSS
const autoprefixer = require("autoprefixer");

// Modern JS minifier
const terser = require("gulp-terser");

// Clean and minify raw CSS
const minifyCSS = require("gulp-clean-css");

// Use Dart Sass to compile SCSS
const sassCompiler = require("sass");
const sass = require("gulp-sass")(sassCompiler);
const sourcemaps = require("gulp-sourcemaps");

// Bootstrap 5.3 + theme @import graph triggers Dart Sass deprecations; silence until BS/@use migration.
const sassCompileOptions = {
  quietDeps: true,
  silenceDeprecations: [
    "color-functions",
    "global-builtin",
    "import",
    "if-function",
    "legacy-js-api",
  ],
};

//==============================
// Folder paths
//==============================
const filePath = {
  base: {
    base: "./",
    node: "./node_modules",
  },
  src: {
    root: "./src",
    basesrcfiles: "./src/**/*",
    css: "./src/assets/css",
    icons: "./src/assets/icons/**/*",
    scss: "./src/assets/scss/**/*.scss",
    js: "./src/assets/js/**/*.js",
    html: "./src/**/*.html",
    assets: "./src/assets/**/*",
    images: "./src/assets/images/**/*",
    vendor: "./src/assets/vendor/**/*",
  },
  temp: {
    basetemp: "./.temp",
  },
  dist: {
    basedist: "./dist",
    js: "./dist/assets/js",
    images: "./dist/assets/images",
    css: "./dist/assets/css",
    icons: "./dist/assets/icons",
    scss: "./dist/assets/scss",
    vendor: "./dist/assets/vendor",
  },
};

//==============================
// HTML Partial Include and Minify
//==============================
function FileIncludeHtml() {
  return src([filePath.src.html, "!./src/**/elements/**/*"])
    .pipe(
      fileinclude({
        prefix: "@@",
        basepath: "@file",
      })
    )
    .pipe(replace(/src="(?:\.\/)?(.*)node_modules/g, 'src="assets/vendor'))
	.pipe(replace(/href="(?:\.\/)?(.*)node_modules/g, 'href="assets/vendor'))
    .pipe(useref())
    .pipe(gulpIf("*.css", postcss([autoprefixer(), cssnano()])))
    .pipe(gulpIf("*.js", terser()))
    .pipe(dest(filePath.dist.basedist))
    .pipe(browserSync.stream());
}

//==============================
// HTML Include for Local Preview
//==============================
function FileTemp() {
  return src([filePath.src.html, "!./src/**/partials/**/*"])
    .pipe(
      fileinclude({
        prefix: "@@",
        basepath: "@file",
      })
    )
    // Same as FileIncludeHtml: map node_modules URLs to assets/vendor so dev server
    // does not request literal "@@webRoot/node_modules/..." (MIME text/html / 404).
    .pipe(replace(/src="(?:\.\/)?(.*)node_modules/g, 'src="assets/vendor'))
    .pipe(replace(/href="(?:\.\/)?(.*)node_modules/g, 'href="assets/vendor'))
    .pipe(dest(filePath.temp.basetemp));
}

function dzPdfjs311ToTemp() {
  return src("src/assets/vendor/pdfjs-3.11/**/*").pipe(dest(".temp/assets/vendor/pdfjs-3.11"));
}

//==============================
// Copy Assets (vendor, js, icons, etc.)
//==============================
function dzAssetsBuild(callback) {
  return (
    src(filePath.src.vendor).pipe(dest(filePath.dist.vendor)),
    
	//src(filePath.src.js).pipe(uglify()).pipe(dest(filePath.dist.js)),
	src(filePath.src.js).pipe(dest(filePath.dist.js)),
    
	src(filePath.src.icons).pipe(dest(filePath.dist.icons)),
    src(filePath.src.scss).pipe(dest(filePath.dist.scss)),
    
	//src(filePath.src.css + "/**/*").pipe(minifyCSS()).pipe(dest(filePath.dist.css))
	src(filePath.src.css + "/**/*").pipe(dest(filePath.dist.css))
  );

  callback();
}

//==============================
// Copy Images
//==============================
function dzImages() {
  return src(filePath.src.images).pipe(dest(filePath.dist.images));
}

//==============================
// Compile SCSS
//==============================
function compileSCSS_LTR() {
  return src([
    "./src/assets/scss/main.scss",
    "./src/assets/scss/plugins.scss",
    "./src/assets/scss/switcher.scss"
  ])
    .pipe(sourcemaps.init())
    .pipe(sass(sassCompileOptions).on("error", sass.logError))
    .pipe(postcss([autoprefixer()]))
    .pipe(rename(function (path) {
      if (path.basename === "main") path.basename = "style";
    }))
    .pipe(sourcemaps.write("."))
    .pipe(dest(filePath.dist.css))
    .pipe(dest(filePath.temp.basetemp + "/assets/css"))
    .pipe(dest(filePath.src.css));
}

function compileSCSS_RTL() {
  return src([
    "./src/assets/scss/main.scss",
    "./src/assets/scss/plugins.scss",
    "./src/assets/scss/switcher.scss"
  ])
    .pipe(sourcemaps.init())
    .pipe(sass(sassCompileOptions).on("error", sass.logError))
    .pipe(postcss([autoprefixer()]))
    .pipe(rtlcss())
    .pipe(rename(function (path) {
      if (path.basename === "main") path.basename = "style-rtl";
      else path.basename += "-rtl";
    }))
    .pipe(sourcemaps.write("."))
    .pipe(dest(filePath.dist.css))
    .pipe(dest(filePath.temp.basetemp + "/assets/css"))
    .pipe(dest(filePath.src.css));
}

const compileSCSS = parallel(compileSCSS_LTR, compileSCSS_RTL);


//==============================
// Copy node_modules libraries to dist/assets/vendor (production + BS fallback)
//==============================
function dzVendor() {
  return src(npmFiles(), { base: filePath.base.node }).pipe(dest(filePath.dist.vendor));
}

//==============================
// Copy same vendor tree into .temp/assets/vendor so BrowserSync's first
// baseDir serves real JS/CSS (avoids HTML 404 / MIME mismatch when .temp is tried first).
//==============================
function dzVendorToTemp() {
  return src(npmFiles(), { base: filePath.base.node }).pipe(
    dest(filePath.temp.basetemp + "/assets/vendor")
  );
}

//==============================
// Copy npm packages into src/assets/vendor so paths like
// ``assets/vendor/apexcharts/dist/apexcharts.min.js`` resolve when the dev
// server root is ``src/`` (Live Server, etc.) — not only ``dist/`` or ``.temp/``.
//==============================
function dzVendorToSrc() {
  return src(npmFiles(), { base: filePath.base.node }).pipe(
    dest(filePath.src.root + "/assets/vendor")
  );
}

//==============================
// Clean temporary preview folder
//==============================
function cleanTemp(callback) {
  del.sync(filePath.temp.basetemp);
  callback();
}

//==============================
// Clean production folder
//==============================
function cleanDist(callback) {
  del.sync(filePath.dist.basedist);
  callback();
}

//==============================
// Live preview with browserSync
//==============================
function browserSyncServe(callback) {
  browserSync.init(
    {
      server: {
        // .temp is listed first for fresh HTML from FileTemp; vendor must exist under
        // .temp/assets/vendor (dzVendorToTemp) so /assets/vendor/* is not a miss/404 HTML page.
        baseDir: [
          filePath.temp.basetemp,
          filePath.dist.basedist,
          filePath.src.root,
          filePath.base.base,
        ],
        middleware: [
          flaskApiProxyMiddleware,
          function drawingViewerRootRedirect(req, res, next) {
            var pathOnly = (req.url || "").split("?")[0];
            if (pathOnly === "/drawing-viewer.html") {
              var q = (req.url || "").indexOf("?") >= 0 ? (req.url || "").slice((req.url || "").indexOf("?")) : "";
              res.writeHead(302, { Location: "/construction/drawing-viewer.html" + q });
              res.end();
              return;
            }
            next();
          },
        ],
      },
      startPath: "/construction/index.html",
      notify: true,
    },
    function (err) {
      if (err) {
        console.error("[W3CRM] BrowserSync failed to start:", err);
      } else {
        try {
          var urls = browserSync.getOption("urls");
          var local = urls && typeof urls.get === "function" ? urls.get("local") : null;
          if (local) {
            console.log("\n[W3CRM] Open this URL (port may differ if 3000 is busy):\n  " + local + "\n");
          }
        } catch (e) {
          /* ignore */
        }
      }
      callback();
    }
  );
}

//==============================
// Reload manually
//==============================
function syncReload(callback) {
  browserSync.reload();
  callback();
}

//==============================
// Watch for changes
//==============================
function watchTask() {
  watch(filePath.src.html, series(FileTemp, syncReload));
  watch(filePath.src.images, series(dzImages));
  watch(filePath.src.scss, series(compileSCSS));
}

//==============================
// Default Task (development)
exports.default = series(
  parallel(FileTemp, dzVendor, dzVendorToTemp, dzVendorToSrc, dzPdfjs311ToTemp),
  browserSyncServe,
  watchTask
);

// Build Task (production)
// Note: do not run cleanTemp here — it deletes ./.temp while BrowserSync (npx gulp)
// uses .temp as the first baseDir; wiping it mid-session breaks previews until FileTemp runs again.
exports.build = series(
  parallel(cleanDist),
  FileIncludeHtml,
  parallel(dzVendor, dzVendorToSrc),
  dzImages,
  compileSCSS,
  dzAssetsBuild
);

// Individual Exports (for CLI)
exports.FileIncludeHtml = FileIncludeHtml;
exports.FileTemp = FileTemp;
exports.dzPdfjs311ToTemp = dzPdfjs311ToTemp;
exports.dzAssetsBuild = dzAssetsBuild;
exports.dzVendor = dzVendor;
exports.dzVendorToTemp = dzVendorToTemp;
exports.dzVendorToSrc = dzVendorToSrc;
exports.cleanTemp = cleanTemp;
exports.cleanDist = cleanDist;
exports.dzImages = dzImages;
