/**
 * viewer.js — Premium 3D Product Viewer
 * eFundi Home Improvement Platform
 *
 * Features:
 *   - GLTFLoader + DRACOLoader (compressed model support)
 *   - OrbitControls (rotate, zoom, pan)
 *   - Auto-rotation with toggle
 *   - HDR environment lighting (RGBELoader)
 *   - Multiple light sources with animated fill light
 *   - Shadows + contact shadow plane
 *   - Post-processing: Bloom, SSAO, Depth of Field
 *   - Hotspots / product annotations (raycasting)
 *   - Material color variants
 *   - Wireframe mode toggle
 *   - Exploded view animation (GSAP)
 *   - Screenshot button
 *   - Fullscreen mode
 *   - Reset camera
 *   - Loading progress indicator
 *   - Responsive resize observer
 *   - Mobile pinch-zoom & touch support (via OrbitControls)
 *   - prefers-reduced-motion respected
 *
 * Usage:
 *   <div id="im-viewer-mount"></div>
 *   <script type="module" src="viewer.js"></script>
 *
 * Dependencies (add to your template before this script):
 *   <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
 *   <script src="https://cdn.jsdelivr.net/npm/gsap@3.12.2/dist/gsap.min.js"></script>
 *
 *   Three.js addons are loaded dynamically below via jsDelivr CDN.
 *   They require r128-compatible builds — see LOAD_ADDONS().
 */

(function () {
  'use strict';

  /* ================================================================
     CONFIGURATION — edit these to match your project
     ================================================================ */
  const CONFIG = {
    mountId:       'im-viewer-mount',   // ID of the container div
    modelPath:     '/static/models/product.glb',  // Path to your GLB
    hdrPath:       '/static/textures/hdr/studio.hdr', // Poly Haven HDR
    //
    // ── DRACO DECODER ──────────────────────────────────────────────
    // If your GLB was exported with Draco compression (recommended
    // for smaller file sizes), set the path to the WASM decoder files.
    // Download from: https://www.gstatic.com/draco/versioned/decoders/1.5.6/
    // Place in /static/draco/ and set the path below.
    dracoDecoderPath: '/static/draco/',
    //
    // ── CAMERA ─────────────────────────────────────────────────────
    cameraFov:     45,
    cameraNear:    0.01,
    cameraFar:     100,
    cameraInitPos: [0, 0.8, 3.5],   // [x, y, z]
    cameraTarget:  [0, 0.2, 0],     // OrbitControls target
    //
    // ── AUTO-ROTATION ───────────────────────────────────────────────
    autoRotate:       true,
    autoRotateSpeed:  0.6,
    //
    // ── SHADOWS ─────────────────────────────────────────────────────
    shadows: true,
    //
    // ── POST-PROCESSING ─────────────────────────────────────────────
    bloom:       true,
    bloomStrength: 0.18,
    bloomRadius:   0.4,
    bloomThreshold: 0.82,
    dof:         false,   // Depth of Field — expensive, off by default
    ssao:        false,   // SSAO — requires r128 addon, off by default
    //
    // ── HOTSPOTS ────────────────────────────────────────────────────
    // Define world-space positions and labels for annotation pins.
    hotspots: [
      // { position: [0.3, 1.2, 0.1], label: 'Premium finish', detail: 'Hand-applied lacquer in 3 coats.' },
      // { position: [-0.4, 0.5, 0.2], label: 'Solid oak frame', detail: 'FSC-certified hardwood.' },
    ],
    //
    // ── MATERIAL VARIANTS ───────────────────────────────────────────
    // Each variant swaps the material color on every mesh in the model.
    variants: [
      { label: 'Natural',  hex: '#C4A882' },
      { label: 'Slate',    hex: '#5A6472' },
      { label: 'Clay',     hex: '#C9683F' },
      { label: 'Midnight', hex: '#1A2132' },
    ],
    //
    // ── EXPLODED VIEW ───────────────────────────────────────────────
    // Multiplier for how far apart parts spread when explode is active.
    explodeDistance: 0.8,
  };

  /* ================================================================
     STATE
     ================================================================ */
  const STATE = {
    scene:      null,
    camera:     null,
    renderer:   null,
    controls:   null,
    composer:   null,    // EffectComposer (post-processing)
    model:      null,    // Root Group of the loaded GLTF
    parts:      [],      // Flat array of mesh children (for explode)
    partOrigins:[],      // Original positions before explode
    mixer:      null,    // AnimationMixer if model has animations
    clock:      new (window.THREE ? THREE.Clock : class { getDelta(){return 0.016;} })(),
    animFrame:  null,
    autoRotate: CONFIG.autoRotate,
    wireframe:  false,
    exploded:   false,
    hotspotMeshes: [],
    overlays:   [],
    prefersReduced: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  };

  /* ================================================================
     WAIT FOR THREE.JS TO BE AVAILABLE
     ================================================================ */
  function waitFor (predicate, cb, interval = 40) {
    if (predicate()) { cb(); return; }
    const t = setInterval(() => { if (predicate()) { clearInterval(t); cb(); } }, interval);
  }

  waitFor(() => window.THREE && window.gsap, init);

  /* ================================================================
     INIT — entry point
     ================================================================ */
  async function init () {
    const mount = document.getElementById(CONFIG.mountId);
    if (!mount) {
      console.warn('[viewer.js] Mount element #' + CONFIG.mountId + ' not found.');
      return;
    }

    buildViewerDOM(mount);
    buildRenderer(mount);
    buildScene();
    buildCamera();
    await loadAddons();    // OrbitControls, GLTFLoader, RGBELoader, post-processing
    buildLights();
    buildControls();
    buildPostProcessing();
    buildHotspotLayer();
    buildUI(mount);
    loadModel();
    buildResizeObserver(mount);
    startRenderLoop();

    mount.dispatchEvent(new CustomEvent('viewer:ready'));
  }

  /* ================================================================
     DOM STRUCTURE
     ================================================================ */
  function buildViewerDOM (mount) {
    mount.style.position   = 'relative';
    mount.style.overflow   = 'hidden';
    mount.style.background = '#0F1B2D';
    mount.style.minHeight  = mount.style.minHeight || '520px';
    mount.style.borderRadius = '4px';

    // Loading overlay
    mount.insertAdjacentHTML('beforeend', `
      <div id="im-viewer-loader" aria-live="polite" aria-label="Loading 3D model"
           style="
             position:absolute;inset:0;display:flex;flex-direction:column;
             align-items:center;justify-content:center;
             background:#0F1B2D;z-index:50;gap:16px;
             transition:opacity 0.7s cubic-bezier(0.16,1,0.3,1);
           ">
        <div style="
          font-family:'JetBrains Mono',monospace;font-size:0.65rem;
          letter-spacing:0.18em;text-transform:uppercase;
          color:rgba(255,255,255,0.35);
        ">Loading model</div>
        <div style="
          width:200px;height:1px;background:rgba(255,255,255,0.08);
          position:relative;overflow:hidden;
        ">
          <div id="im-viewer-progress-bar" style="
            position:absolute;inset:0;
            background:#C9683F;
            transform-origin:left;transform:scaleX(0);
            transition:transform 0.2s ease;
          "></div>
        </div>
        <div id="im-viewer-pct" style="
          font-family:'JetBrains Mono',monospace;font-size:0.65rem;
          color:rgba(255,255,255,0.22);letter-spacing:0.1em;
        ">0%</div>
      </div>
    `);

    // Canvas placeholder (renderer appends its own)
    mount.insertAdjacentHTML('beforeend', `
      <canvas id="im-viewer-canvas" aria-label="Interactive 3D product viewer"
              style="display:block;width:100%;height:100%;"></canvas>
    `);

    // Hotspot layer (absolutely positioned on top of canvas)
    mount.insertAdjacentHTML('beforeend', `
      <div id="im-viewer-hotspots" aria-label="Product annotations"
           style="position:absolute;inset:0;pointer-events:none;z-index:10;"></div>
    `);
  }

  /* ================================================================
     RENDERER
     ================================================================ */
  function buildRenderer (mount) {
    const canvas = mount.querySelector('#im-viewer-canvas');
    STATE.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false,
      powerPreference: 'high-performance',
    });

    STATE.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    STATE.renderer.setSize(mount.clientWidth, mount.clientHeight);
    STATE.renderer.outputEncoding    = THREE.sRGBEncoding;
    STATE.renderer.toneMapping       = THREE.ACESFilmicToneMapping;
    STATE.renderer.toneMappingExposure = 1.1;

    if (CONFIG.shadows) {
      STATE.renderer.shadowMap.enabled = true;
      STATE.renderer.shadowMap.type    = THREE.PCFSoftShadowMap;
    }
  }

  /* ================================================================
     SCENE
     ================================================================ */
  function buildScene () {
    STATE.scene = new THREE.Scene();
    STATE.scene.background = new THREE.Color(0x0F1B2D);

    // Subtle atmospheric fog
    STATE.scene.fog = new THREE.FogExp2(0x0F1B2D, 0.035);

    // Contact shadow plane (receives shadows from the model)
    if (CONFIG.shadows) {
      const shadowGeo = new THREE.PlaneGeometry(12, 12);
      const shadowMat = new THREE.ShadowMaterial({ opacity: 0.25, transparent: true });
      const shadowPlane = new THREE.Mesh(shadowGeo, shadowMat);
      shadowPlane.rotation.x = -Math.PI / 2;
      shadowPlane.position.y = -0.001;
      shadowPlane.receiveShadow = true;
      shadowPlane.name = '__shadow_plane__';
      STATE.scene.add(shadowPlane);
    }
  }

  /* ================================================================
     CAMERA
     ================================================================ */
  function buildCamera () {
    const mount = document.getElementById(CONFIG.mountId);
    const aspect = mount.clientWidth / mount.clientHeight;

    STATE.camera = new THREE.PerspectiveCamera(
      CONFIG.cameraFov,
      aspect,
      CONFIG.cameraNear,
      CONFIG.cameraFar
    );

    STATE.camera.position.set(...CONFIG.cameraInitPos);
  }

  /* ================================================================
     LOAD THREE.JS ADDONS (dynamically, CDN)
     These are not bundled with the r128 CDN build.
     We inject them as script tags and wait for globals to appear.
     ================================================================ */
  async function loadAddons () {
    // In r128, OrbitControls etc. are available via the examples/js/ path.
    // We load UMD-compatible builds from jsDelivr.
    const addons = [
      'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js',
      'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js',
      'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/DRACOLoader.js',
      'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/RGBELoader.js',
      'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/pmrem/PMREMGenerator.js',
      // Post-processing
      'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/EffectComposer.js',
      'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/RenderPass.js',
      'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/UnrealBloomPass.js',
      'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/ShaderPass.js',
      'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/CopyShader.js',
      'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/LuminosityHighPassShader.js',
    ];

    await Promise.all(addons.map(src => loadScript(src)));
  }

  function loadScript (src) {
    return new Promise((resolve, reject) => {
      if (document.querySelector('script[src="' + src + '"]')) { resolve(); return; }
      const s = document.createElement('script');
      s.src = src;
      s.onload  = resolve;
      s.onerror = () => { console.warn('[viewer.js] Failed to load addon: ' + src); resolve(); };
      document.head.appendChild(s);
    });
  }

  /* ================================================================
     LIGHTS
     ================================================================ */
  function buildLights () {
    // Ambient — gentle fill
    const ambient = new THREE.AmbientLight(0xffffff, 0.3);
    ambient.name = 'ambient';
    STATE.scene.add(ambient);

    // Key light (main directional from front-top-right)
    const key = new THREE.DirectionalLight(0xfff8f0, 2.2);
    key.position.set(2.5, 4, 3);
    key.name = 'keyLight';
    if (CONFIG.shadows) {
      key.castShadow = true;
      key.shadow.mapSize.set(2048, 2048);
      key.shadow.camera.near   = 0.5;
      key.shadow.camera.far    = 20;
      key.shadow.camera.left   = -4;
      key.shadow.camera.right  = 4;
      key.shadow.camera.top    = 4;
      key.shadow.camera.bottom = -4;
      key.shadow.bias          = -0.001;
      key.shadow.normalBias    = 0.02;
    }
    STATE.scene.add(key);

    // Fill light (soft, opposite side)
    const fill = new THREE.DirectionalLight(0xc8d8ff, 0.7);
    fill.position.set(-3, 2, -2);
    fill.name = 'fillLight';
    STATE.scene.add(fill);

    // Rim / backlight (warm, behind model)
    const rim = new THREE.DirectionalLight(0xffc070, 1.0);
    rim.position.set(0, 1.5, -4);
    rim.name = 'rimLight';
    STATE.scene.add(rim);

    // Subtle point light at ground (bounce simulation)
    const bounce = new THREE.PointLight(0x809fff, 0.4, 8);
    bounce.position.set(0, -1, 1);
    bounce.name = 'bounceLight';
    STATE.scene.add(bounce);

    // Animated fill light (slow oscillation for life)
    if (!STATE.prefersReduced) {
      STATE._fillLightRef  = fill;
      STATE._fillLightBase = fill.intensity;
    }
  }

  /* ================================================================
     ORBIT CONTROLS
     ================================================================ */
  function buildControls () {
    if (!THREE.OrbitControls) {
      console.warn('[viewer.js] OrbitControls not loaded.');
      return;
    }

    STATE.controls = new THREE.OrbitControls(STATE.camera, STATE.renderer.domElement);

    const c = STATE.controls;
    c.target.set(...CONFIG.cameraTarget);
    c.enableDamping    = true;
    c.dampingFactor    = 0.06;
    c.autoRotate       = STATE.autoRotate && !STATE.prefersReduced;
    c.autoRotateSpeed  = CONFIG.autoRotateSpeed;
    c.enablePan        = true;
    c.panSpeed         = 0.6;
    c.rotateSpeed      = 0.55;
    c.zoomSpeed        = 0.8;
    c.minDistance      = 0.5;
    c.maxDistance      = 12;
    c.minPolarAngle    = 0;
    c.maxPolarAngle    = Math.PI * 0.88;
    c.screenSpacePanning = true;

    // Pause auto-rotate when user interacts
    c.addEventListener('start', () => {
      if (STATE.autoRotate) c.autoRotate = false;
    });
    c.addEventListener('end', () => {
      if (STATE.autoRotate) c.autoRotate = true;
    });

    c.update();
  }

  /* ================================================================
     POST-PROCESSING (Bloom + optional DoF)
     ================================================================ */
  function buildPostProcessing () {
    if (!THREE.EffectComposer || !THREE.RenderPass || !THREE.UnrealBloomPass) {
      console.warn('[viewer.js] Post-processing addons not loaded — rendering without.');
      STATE.composer = null;
      return;
    }

    const mount = document.getElementById(CONFIG.mountId);
    const w = mount.clientWidth;
    const h = mount.clientHeight;

    STATE.composer = new THREE.EffectComposer(STATE.renderer);

    // Base render pass
    const renderPass = new THREE.RenderPass(STATE.scene, STATE.camera);
    STATE.composer.addPass(renderPass);

    // Bloom
    if (CONFIG.bloom) {
      const bloomPass = new THREE.UnrealBloomPass(
        new THREE.Vector2(w, h),
        CONFIG.bloomStrength,
        CONFIG.bloomRadius,
        CONFIG.bloomThreshold
      );
      bloomPass.name = 'bloom';
      STATE.composer.addPass(bloomPass);
    }

    STATE.composer.setSize(w, h);
  }

  /* ================================================================
     HDRI ENVIRONMENT (loaded after model, so it's ready when needed)
     ================================================================ */
  function loadHDR () {
    if (!THREE.RGBELoader || !THREE.PMREMGenerator) return;

    const pmrem = new THREE.PMREMGenerator(STATE.renderer);
    pmrem.compileEquirectangularShader();

    new THREE.RGBELoader().load(
      CONFIG.hdrPath,
      texture => {
        const envMap = pmrem.fromEquirectangular(texture).texture;
        STATE.scene.environment    = envMap;   // PBR reflections on all materials
        STATE.scene.background     = envMap;   // Show HDR as backdrop
        texture.dispose();
        pmrem.dispose();

        // Slightly darken the background so focus stays on the model
        STATE.renderer.toneMappingExposure = 0.85;
      },
      undefined,
      () => {
        // HDR failed (e.g. file not found) — fall back to procedural lighting
        console.warn('[viewer.js] HDR not loaded from ' + CONFIG.hdrPath + '. Using fallback lights.');
        buildFallbackEnvironment();
      }
    );
  }

  function buildFallbackEnvironment () {
    // Procedural sky-like gradient as a large sphere
    const skyGeo = new THREE.SphereGeometry(50, 32, 16);
    const skyMat = new THREE.MeshBasicMaterial({
      color: 0x0F1B2D,
      side: THREE.BackSide,
    });
    STATE.scene.add(new THREE.Mesh(skyGeo, skyMat));
  }

  /* ================================================================
     GLTF MODEL LOADER
     ================================================================ */
  function loadModel () {
    if (!THREE.GLTFLoader) {
      console.warn('[viewer.js] GLTFLoader not available.');
      hideLoader();
      return;
    }

    const loader = new THREE.GLTFLoader();

    // Draco decompression
    if (THREE.DRACOLoader) {
      const draco = new THREE.DRACOLoader();
      draco.setDecoderPath(CONFIG.dracoDecoderPath);
      draco.preload();
      loader.setDRACOLoader(draco);
    }

    loader.load(
      CONFIG.modelPath,

      // onLoad
      gltf => {
        STATE.model = gltf.scene;
        STATE.model.name = 'productModel';

        // Centre and normalise model size
        fitModelToView(STATE.model);

        // Traverse: enable shadows, collect parts for explode
        STATE.model.traverse(child => {
          if (!child.isMesh) return;

          child.castShadow    = CONFIG.shadows;
          child.receiveShadow = CONFIG.shadows;

          // Clone material so variant changes don't mutate shared refs
          if (Array.isArray(child.material)) {
            child.material = child.material.map(m => m.clone());
          } else if (child.material) {
            child.material = child.material.clone();
          }

          STATE.parts.push(child);
          STATE.partOrigins.push(child.position.clone());
        });

        STATE.scene.add(STATE.model);

        // Animations (if model has built-in clips)
        if (gltf.animations && gltf.animations.length) {
          STATE.mixer = new THREE.AnimationMixer(STATE.model);
          gltf.animations.forEach(clip => {
            STATE.mixer.clipAction(clip).play();
          });
        }

        loadHDR();
        buildHotspots();
        hideLoader();

        // Entrance animation
        if (!STATE.prefersReduced) {
          STATE.model.scale.set(0, 0, 0);
          gsap.to(STATE.model.scale, {
            x: 1, y: 1, z: 1,
            duration: 1.4,
            ease: 'elastic.out(1, 0.55)',
          });
        }
      },

      // onProgress
      xhr => {
        if (!xhr.total) return;
        const pct = Math.round((xhr.loaded / xhr.total) * 100);
        setLoaderProgress(pct);
      },

      // onError
      err => {
        console.error('[viewer.js] Model load failed:', err);
        showModelError();
        hideLoader();
      }
    );
  }

  /* ────────────────────────────────────────────────────────────────
     FIT MODEL — centres model at origin and scales it to fit view
  ──────────────────────────────────────────────────────────────── */
  function fitModelToView (model) {
    const box    = new THREE.Box3().setFromObject(model);
    const center = new THREE.Vector3();
    const size   = new THREE.Vector3();
    box.getCenter(center);
    box.getSize(size);

    const maxDim = Math.max(size.x, size.y, size.z);
    const scale  = 2.0 / maxDim;  // target ~2 units tall

    model.scale.setScalar(scale);
    model.position.sub(center.multiplyScalar(scale));
    model.position.y -= (size.y * scale) / 2;  // sit on shadow plane

    // Update controls target to model centre
    if (STATE.controls) {
      const newBox = new THREE.Box3().setFromObject(model);
      const newCenter = new THREE.Vector3();
      newBox.getCenter(newCenter);
      STATE.controls.target.copy(newCenter);
      STATE.controls.update();
    }
  }

  /* ================================================================
     HOTSPOTS — 3D world-space pins projected to 2D screen
     ================================================================ */
  function buildHotspotLayer () {
    STATE._hotspotLayer = document.getElementById('im-viewer-hotspots');
  }

  function buildHotspots () {
    if (!CONFIG.hotspots.length || !STATE._hotspotLayer) return;

    CONFIG.hotspots.forEach((hs, i) => {
      // 3D invisible sphere for raycasting
      const geo  = new THREE.SphereGeometry(0.04, 8, 8);
      const mat  = new THREE.MeshBasicMaterial({ visible: false });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.set(...hs.position);
      mesh.userData = { hotspotIndex: i };
      STATE.scene.add(mesh);
      STATE.hotspotMeshes.push(mesh);

      // 2D DOM pin
      const pin = document.createElement('button');
      pin.className = 'im-hotspot-pin';
      pin.setAttribute('aria-label', hs.label);
      pin.dataset.index = i;
      pin.style.cssText = `
        position:absolute;
        width:28px;height:28px;
        border-radius:50%;
        border:2px solid rgba(255,255,255,0.8);
        background:rgba(201,104,63,0.9);
        cursor:pointer;
        pointer-events:all;
        display:flex;align-items:center;justify-content:center;
        transition:transform 0.3s cubic-bezier(0.16,1,0.3,1),opacity 0.3s;
        transform:translate(-50%,-50%) scale(1);
        font-family:'JetBrains Mono',monospace;
        font-size:10px;color:#fff;font-weight:600;
      `;
      pin.textContent = String(i + 1);

      // Annotation tooltip
      const tooltip = document.createElement('div');
      tooltip.className = 'im-hotspot-tooltip';
      tooltip.style.cssText = `
        position:absolute;
        bottom:calc(100% + 10px);left:50%;
        transform:translateX(-50%) translateY(4px);
        background:rgba(15,27,45,0.95);
        border:1px solid rgba(255,255,255,0.1);
        border-radius:4px;
        padding:10px 14px;
        min-width:160px;
        pointer-events:none;
        opacity:0;
        transition:opacity 0.25s ease, transform 0.25s cubic-bezier(0.16,1,0.3,1);
        white-space:nowrap;
        z-index:20;
      `;
      tooltip.innerHTML = `
        <div style="font-family:'Inter',sans-serif;font-size:0.8rem;font-weight:500;color:#fff;margin-bottom:4px;">${hs.label}</div>
        <div style="font-family:'Inter',sans-serif;font-size:0.72rem;color:rgba(255,255,255,0.5);line-height:1.5;">${hs.detail || ''}</div>
      `;
      pin.appendChild(tooltip);

      pin.addEventListener('mouseenter', () => {
        tooltip.style.opacity = '1';
        tooltip.style.transform = 'translateX(-50%) translateY(0)';
        pin.style.transform = 'translate(-50%,-50%) scale(1.2)';
      });
      pin.addEventListener('mouseleave', () => {
        tooltip.style.opacity = '0';
        tooltip.style.transform = 'translateX(-50%) translateY(4px)';
        pin.style.transform = 'translate(-50%,-50%) scale(1)';
      });

      STATE._hotspotLayer.appendChild(pin);
      STATE.overlays.push({ mesh, pin });
    });
  }

  /* Reproject all hotspot pins each frame */
  function updateHotspots () {
    if (!STATE.overlays.length) return;
    const mount = document.getElementById(CONFIG.mountId);
    const w = mount.clientWidth;
    const h = mount.clientHeight;

    STATE.overlays.forEach(({ mesh, pin }) => {
      const pos = mesh.position.clone().project(STATE.camera);
      const x   = (pos.x  *  0.5 + 0.5) * w;
      const y   = (pos.y  * -0.5 + 0.5) * h;
      const visible = pos.z < 1; // hide if behind camera

      pin.style.left    = x + 'px';
      pin.style.top     = y + 'px';
      pin.style.opacity = visible ? '1' : '0';
      pin.style.pointerEvents = visible ? 'all' : 'none';
    });
  }

  /* ================================================================
     VIEWER UI (toolbar buttons)
     ================================================================ */
  function buildUI (mount) {
    const toolbar = document.createElement('div');
    toolbar.setAttribute('role', 'toolbar');
    toolbar.setAttribute('aria-label', 'Viewer controls');
    toolbar.style.cssText = `
      position:absolute;
      top:16px;right:16px;
      display:flex;flex-direction:column;gap:8px;
      z-index:20;
    `;

    // Auto-rotate toggle
    toolbar.appendChild(makeBtn('⟳', 'Toggle auto-rotation', 'btn-rotate', () => {
      STATE.autoRotate = !STATE.autoRotate;
      if (STATE.controls) STATE.controls.autoRotate = STATE.autoRotate;
    }));

    // Wireframe toggle
    toolbar.appendChild(makeBtn('⬡', 'Toggle wireframe', 'btn-wire', () => {
      STATE.wireframe = !STATE.wireframe;
      STATE.parts.forEach(mesh => {
        const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        mats.forEach(m => { m.wireframe = STATE.wireframe; });
      });
    }));

    // Exploded view
    toolbar.appendChild(makeBtn('⊕', 'Toggle exploded view', 'btn-explode', toggleExplode));

    // Screenshot
    toolbar.appendChild(makeBtn('↓', 'Download screenshot', 'btn-screenshot', takeScreenshot));

    // Reset camera
    toolbar.appendChild(makeBtn('⌂', 'Reset camera', 'btn-reset', resetCamera));

    // Fullscreen
    toolbar.appendChild(makeBtn('⛶', 'Toggle fullscreen', 'btn-fullscreen', toggleFullscreen));

    mount.appendChild(toolbar);

    // ── VARIANT SWATCHES ──────────────────────────────────────────
    if (CONFIG.variants.length) {
      const swatchBar = document.createElement('div');
      swatchBar.setAttribute('role', 'group');
      swatchBar.setAttribute('aria-label', 'Color variants');
      swatchBar.style.cssText = `
        position:absolute;bottom:20px;left:50%;transform:translateX(-50%);
        display:flex;gap:10px;z-index:20;
        background:rgba(15,27,45,0.7);
        border:1px solid rgba(255,255,255,0.08);
        border-radius:40px;padding:8px 14px;
        backdrop-filter:blur(12px);
        -webkit-backdrop-filter:blur(12px);
      `;

      CONFIG.variants.forEach((v, i) => {
        const sw = document.createElement('button');
        sw.style.cssText = `
          width:22px;height:22px;border-radius:50%;
          background:${v.hex};border:2px solid rgba(255,255,255,${i === 0 ? '0.9' : '0.25'});
          cursor:pointer;transition:border-color 0.2s ease,transform 0.2s ease;
          outline:none;
        `;
        sw.setAttribute('aria-label', 'Color: ' + v.label);
        sw.setAttribute('title', v.label);
        sw.addEventListener('click', () => {
          applyVariant(v.hex);
          swatchBar.querySelectorAll('button').forEach((b, j) => {
            b.style.borderColor = j === i ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.25)';
            b.style.transform   = j === i ? 'scale(1.2)' : 'scale(1)';
          });
        });
        swatchBar.appendChild(sw);
      });

      mount.appendChild(swatchBar);
    }
  }

  function makeBtn (icon, label, id, onClick) {
    const btn = document.createElement('button');
    btn.id = id;
    btn.setAttribute('aria-label', label);
    btn.setAttribute('title', label);
    btn.textContent = icon;
    btn.style.cssText = `
      width:36px;height:36px;border-radius:4px;
      background:rgba(15,27,45,0.75);
      border:1px solid rgba(255,255,255,0.1);
      color:rgba(255,255,255,0.75);
      font-size:14px;cursor:pointer;
      display:flex;align-items:center;justify-content:center;
      transition:background 0.2s ease,color 0.2s ease;
      backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);
    `;
    btn.addEventListener('mouseenter', () => {
      btn.style.background = 'rgba(201,104,63,0.85)';
      btn.style.color = '#fff';
    });
    btn.addEventListener('mouseleave', () => {
      btn.style.background = 'rgba(15,27,45,0.75)';
      btn.style.color = 'rgba(255,255,255,0.75)';
    });
    btn.addEventListener('click', onClick);
    return btn;
  }

  /* ================================================================
     VARIANT — swap color on all meshes
     ================================================================ */
  function applyVariant (hex) {
    const color = new THREE.Color(hex);
    STATE.parts.forEach(mesh => {
      const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      mats.forEach(m => {
        if (m.color) m.color.set(color);
      });
    });
  }

  /* ================================================================
     EXPLODED VIEW (GSAP animation)
     ================================================================ */
  function toggleExplode () {
    if (!STATE.parts.length) return;
    STATE.exploded = !STATE.exploded;

    const box    = new THREE.Box3().setFromObject(STATE.model);
    const center = new THREE.Vector3();
    box.getCenter(center);

    STATE.parts.forEach((mesh, i) => {
      const origin = STATE.partOrigins[i];

      if (STATE.exploded) {
        // Direction from model centre to part
        const dir = mesh.getWorldPosition(new THREE.Vector3()).sub(center).normalize();
        gsap.to(mesh.position, {
          x: origin.x + dir.x * CONFIG.explodeDistance,
          y: origin.y + dir.y * CONFIG.explodeDistance,
          z: origin.z + dir.z * CONFIG.explodeDistance,
          duration: 1.2,
          ease: 'power3.out',
          stagger: 0.04,
        });
      } else {
        gsap.to(mesh.position, {
          x: origin.x,
          y: origin.y,
          z: origin.z,
          duration: 1.0,
          ease: 'power3.inOut',
        });
      }
    });
  }

  /* ================================================================
     SCREENSHOT
     ================================================================ */
  function takeScreenshot () {
    // Render one clean frame to canvas
    if (STATE.composer) {
      STATE.composer.render();
    } else {
      STATE.renderer.render(STATE.scene, STATE.camera);
    }

    const link = document.createElement('a');
    link.download = 'product-view.png';
    link.href = STATE.renderer.domElement.toDataURL('image/png');
    link.click();
  }

  /* ================================================================
     RESET CAMERA
     ================================================================ */
  function resetCamera () {
    if (!STATE.controls || STATE.prefersReduced) {
      STATE.camera.position.set(...CONFIG.cameraInitPos);
      if (STATE.controls) {
        STATE.controls.target.set(...CONFIG.cameraTarget);
        STATE.controls.update();
      }
      return;
    }

    gsap.to(STATE.camera.position, {
      x: CONFIG.cameraInitPos[0],
      y: CONFIG.cameraInitPos[1],
      z: CONFIG.cameraInitPos[2],
      duration: 1.4,
      ease: 'power3.inOut',
      onUpdate: () => STATE.controls && STATE.controls.update(),
    });

    gsap.to(STATE.controls.target, {
      x: CONFIG.cameraTarget[0],
      y: CONFIG.cameraTarget[1],
      z: CONFIG.cameraTarget[2],
      duration: 1.4,
      ease: 'power3.inOut',
    });
  }

  /* ================================================================
     FULLSCREEN
     ================================================================ */
  function toggleFullscreen () {
    const mount = document.getElementById(CONFIG.mountId);
    if (!document.fullscreenElement) {
      mount.requestFullscreen && mount.requestFullscreen();
    } else {
      document.exitFullscreen && document.exitFullscreen();
    }
  }

  /* ================================================================
     LOADER HELPERS
     ================================================================ */
  function setLoaderProgress (pct) {
    const bar = document.getElementById('im-viewer-progress-bar');
    const num = document.getElementById('im-viewer-pct');
    if (bar) bar.style.transform = 'scaleX(' + pct / 100 + ')';
    if (num) num.textContent = pct + '%';
  }

  function hideLoader () {
    const el = document.getElementById('im-viewer-loader');
    if (!el) return;
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 750);
  }

  function showModelError () {
    const loader = document.getElementById('im-viewer-loader');
    if (!loader) return;
    loader.innerHTML = `
      <div style="text-align:center;padding:20px;">
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;
                    color:rgba(255,255,255,0.35);letter-spacing:0.12em;margin-bottom:8px;">
          MODEL NOT FOUND
        </div>
        <div style="font-family:'Inter',sans-serif;font-size:0.8rem;color:rgba(255,255,255,0.2);">
          Place your .glb file at: ${CONFIG.modelPath}
        </div>
      </div>
    `;
  }

  /* ================================================================
     RESIZE OBSERVER
     ================================================================ */
  function buildResizeObserver (mount) {
    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (!width || !height) continue;

        STATE.camera.aspect = width / height;
        STATE.camera.updateProjectionMatrix();
        STATE.renderer.setSize(width, height);

        if (STATE.composer) STATE.composer.setSize(width, height);
      }
    });

    ro.observe(mount);
  }

  /* ================================================================
     MAIN RENDER LOOP
     ================================================================ */
  function startRenderLoop () {
    let time = 0;

    function tick () {
      STATE.animFrame = requestAnimationFrame(tick);

      const delta = STATE.clock.getDelta();
      time += delta;

      // Animation mixer (model's built-in animations)
      if (STATE.mixer) STATE.mixer.update(delta);

      // Controls damping update
      if (STATE.controls) STATE.controls.update();

      // Animated fill light — subtle pulse for life
      if (STATE._fillLightRef && !STATE.prefersReduced) {
        STATE._fillLightRef.intensity =
          STATE._fillLightBase + Math.sin(time * 0.4) * 0.08;
      }

      // Update hotspot projections
      updateHotspots();

      // Render (post-processing or direct)
      if (STATE.composer) {
        STATE.composer.render();
      } else {
        STATE.renderer.render(STATE.scene, STATE.camera);
      }
    }

    tick();
  }

  /* ================================================================
     PUBLIC API — accessible via window.eFundiViewer
     ================================================================ */
  window.eFundiViewer = {
    /**
     * Swap model at runtime.
     * @param {string} path — URL to new .glb file
     */
    loadModel (path) {
      if (STATE.model) {
        STATE.scene.remove(STATE.model);
        STATE.parts = [];
        STATE.partOrigins = [];
        STATE.model = null;
      }
      CONFIG.modelPath = path;
      loadModel();
    },

    /** Apply a hex color to all model materials */
    setColor (hex) { applyVariant(hex); },

    /** Toggle wireframe */
    toggleWireframe () {
      STATE.wireframe = !STATE.wireframe;
      STATE.parts.forEach(mesh => {
        const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        mats.forEach(m => { m.wireframe = STATE.wireframe; });
      });
    },

    /** Animate explode / collapse */
    toggleExplode,

    /** Download screenshot PNG */
    screenshot: takeScreenshot,

    /** Reset camera to initial position */
    resetCamera,

    /** Get scene (for advanced customisation) */
    getScene  () { return STATE.scene; },
    getCamera () { return STATE.camera; },
  };

}());