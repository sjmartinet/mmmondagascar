/* Visualizador de voz.
 *
 * Sustituye al personaje 3D por una animacion abstracta que reacciona a la voz:
 * un nucleo que respira, ondas que se expanden mientras habla y una barra de
 * espectro debajo. Todo en un <canvas> de 2D, sin ninguna libreria.
 *
 * Motivo: pesa 6 KB en vez de 670 KB, arranca al instante en cualquier maquina
 * y no depende de WebGL. Menos cosas que puedan fallar delante del jurado.
 *
 * Mantiene la misma API que usaba el avatar:
 *   Avatar.iniciar(canvas)
 *   Avatar.hablar(true|false)
 *   Avatar.nivel = 0..1
 *   Avatar.gesto("saludo" | "explicar" | "negar")
 */
window.Avatar = (function () {
  let lienzo, ctx, ancho, alto, inicio;
  let hablando = false;
  let iniciado = false;
  let suavizado = 0;
  let ondas = [];
  let tono = "#4f46e5"; // indigo por defecto; el gesto "negar" lo vuelve ambar
  let barras = new Array(48).fill(0);

  function redimensionar() {
    const dpr = Math.min(devicePixelRatio || 1, 2);
    ancho = lienzo.clientWidth;
    alto = lienzo.clientHeight;
    lienzo.width = ancho * dpr;
    lienzo.height = alto * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function hexARgba(hex, alfa) {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alfa})`;
  }

  function pintar(t) {
    requestAnimationFrame(pintar);
    if (!ancho || !alto) return;

    const s = (t - inicio) / 1000;
    const cx = ancho / 2;
    const cy = alto / 2 - 10;
    const base = Math.min(ancho, alto) * 0.17;

    // El nivel real del audio manda; si no hay audio, oscila solo mientras habla.
    let objetivo = 0;
    if (hablando) {
      objetivo =
        Avatar.nivel > 0.001
          ? Avatar.nivel
          : 0.35 + Math.sin(s * 11) * 0.2 + Math.sin(s * 6.3) * 0.12;
    }
    suavizado += (Math.max(0, Math.min(1, objetivo)) - suavizado) * 0.18;

    ctx.clearRect(0, 0, ancho, alto);

    /* --- Ondas que se expanden --- */
    if (hablando && s * 60 % 22 < 1) {
      ondas.push({ r: base, vida: 1 });
    }
    ondas = ondas.filter((o) => o.vida > 0);
    ondas.forEach((o) => {
      o.r += 1.6 + suavizado * 2.2;
      o.vida -= 0.011;
      ctx.beginPath();
      ctx.arc(cx, cy, o.r, 0, Math.PI * 2);
      ctx.strokeStyle = hexARgba(tono, o.vida * 0.28);
      ctx.lineWidth = 1.5;
      ctx.stroke();
    });

    /* --- Halo suave --- */
    const radio = base * (1 + suavizado * 0.45) + Math.sin(s * 1.4) * 3;
    const halo = ctx.createRadialGradient(cx, cy, radio * 0.2, cx, cy, radio * 2.6);
    halo.addColorStop(0, hexARgba(tono, 0.18 + suavizado * 0.2));
    halo.addColorStop(1, hexARgba(tono, 0));
    ctx.fillStyle = halo;
    ctx.beginPath();
    ctx.arc(cx, cy, radio * 2.6, 0, Math.PI * 2);
    ctx.fill();

    /* --- Nucleo: circulo deformado por la voz --- */
    ctx.beginPath();
    const puntos = 96;
    for (let i = 0; i <= puntos; i++) {
      const a = (i / puntos) * Math.PI * 2;
      // Tres senos desfasados: el borde ondula de forma organica, no mecanica.
      const deform =
        Math.sin(a * 3 + s * 2.1) * 0.05 +
        Math.sin(a * 5 - s * 1.5) * 0.035 +
        Math.sin(a * 2 + s * 3.2) * 0.04 * suavizado;
      const r = radio * (1 + deform + suavizado * 0.1);
      const x = cx + Math.cos(a) * r;
      const y = cy + Math.sin(a) * r;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.closePath();
    const relleno = ctx.createLinearGradient(cx - radio, cy - radio, cx + radio, cy + radio);
    relleno.addColorStop(0, tono);
    relleno.addColorStop(1, tono === "#4f46e5" ? "#06b6d4" : "#f59e0b");
    ctx.fillStyle = relleno;
    ctx.fill();

    /* --- Espectro debajo --- */
    const anchoB = 3;
    const hueco = 4;
    const totalB = barras.length * (anchoB + hueco) - hueco;
    const x0 = cx - totalB / 2;
    const yB = cy + base * 2.5;
    for (let i = 0; i < barras.length; i++) {
      const centro = 1 - Math.abs(i - barras.length / 2) / (barras.length / 2);
      const objetivoB = hablando
        ? suavizado * (0.35 + centro * 0.9) * (0.55 + Math.abs(Math.sin(s * 9 + i * 0.6)) * 0.75)
        : 0.02;
      barras[i] += (objetivoB - barras[i]) * 0.25;
      const h = Math.max(2, barras[i] * base * 1.15);
      ctx.fillStyle = hexARgba(tono, 0.2 + barras[i] * 0.7);
      ctx.beginPath();
      const x = x0 + i * (anchoB + hueco);
      if (ctx.roundRect) {
        ctx.roundRect(x, yB - h / 2, anchoB, h, anchoB / 2);
        ctx.fill();
      } else {
        ctx.fillRect(x, yB - h / 2, anchoB, h);
      }
    }
  }

  return {
    nivel: 0,

    iniciar: function (elemento) {
      if (iniciado || !elemento || !elemento.getContext) return false;
      lienzo = elemento;
      ctx = lienzo.getContext("2d");
      if (!ctx) return false;
      inicio = performance.now();
      redimensionar();
      addEventListener("resize", redimensionar);
      iniciado = true;
      requestAnimationFrame(pintar);
      return true;
    },

    hablar: function (activo) {
      hablando = !!activo;
      if (!activo) Avatar.nivel = 0;
    },

    gesto: function (nombre) {
      // El color comunica el tipo de respuesta antes de leer una sola palabra.
      tono = nombre === "negar" ? "#d97706" : "#4f46e5";
      if (iniciado) ondas.push({ r: 10, vida: 1 });
    },

    listo: function () {
      return iniciado;
    },
  };
})();
