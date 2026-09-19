/* Logica de la conversacion: consulta, respuesta, voz y subtitulos. */
(function () {
  "use strict";

  const $ = (s) => document.querySelector(s);
  const conversacion = $("#conversacion");
  const formulario = $("#formulario");
  const campo = $("#texto");
  const boton = $("#enviar");
  const estado = $("#estado");
  const subtitulos = $("#subtitulos");
  const lineaSub = subtitulos.querySelector("p");

  let ocupado = false;
  let audioActual = null;
  let contextoAudio = null;
  let temporizadores = [];

  /* ---------------- Arranque ---------------- */
  if (Avatar.iniciar($("#lienzo"))) {
    setTimeout(() => Avatar.gesto("saludo"), 700);
  } else {
    // Si el canvas no esta disponible, la asesoria sigue siendo plenamente usable.
    $("#lienzo").style.display = "none";
  }

  fetch("/api/salud")
    .then((r) => r.json())
    .then((d) => {
      normasCargadas = d.normas_indexadas;
      fishAnunciado = d.voz_disponible;
      // Sin llave de IA la aplicacion NO esta rota: responde desde el corpus.
      // Anunciarlo como un error asustaba a quien la abria por primera vez.
      conIA = d.llave_claude;
      pintarEstado();
    })
    .catch(() => (estado.textContent = "Sin conexion con el servidor"));

  /* ---------------- Subtitulos sincronizados ---------------- */
  function limpiarTemporizadores() {
    temporizadores.forEach(clearTimeout);
    temporizadores = [];
  }

  function mostrarSubtitulos(texto, duracionMs) {
    limpiarTemporizadores();
    // Partimos en frases cortas: leer un parrafo entero de golpe es incomodo.
    const trozos = texto
      .split(/(?<=[.;:!?])\s+/)
      .flatMap((f) => (f.length > 90 ? f.split(/,\s+/) : [f]))
      .map((f) => f.trim())
      .filter(Boolean);
    if (!trozos.length) return;

    const total = trozos.reduce((s, t) => s + t.length, 0);
    subtitulos.classList.remove("oculto");

    let transcurrido = 0;
    trozos.forEach((trozo) => {
      const inicio = transcurrido;
      temporizadores.push(setTimeout(() => (lineaSub.textContent = trozo), inicio));
      transcurrido += (trozo.length / total) * duracionMs;
    });
    temporizadores.push(
      setTimeout(() => {
        subtitulos.classList.add("oculto");
        Avatar.hablar(false);
      }, duracionMs + 400)
    );
  }

  /* ---------------- Voz ---------------- */
  // Chrome devuelve una lista vacia la primera vez que se piden las voces y las
  // carga despues, de forma asincrona. Sin escuchar "voiceschanged" acabariamos
  // narrando espanol con la voz inglesa por defecto.
  let vozElegida = null;
  let normasCargadas = 0;
  let fishAnunciado = false;
  let conIA = false;
  let fishComprobado = false; // solo decimos "Fish Audio" cuando ha devuelto audio

  function nombreCorto(v) {
    // "Microsoft Dalia Online (Natural) - Spanish (Mexico)" -> "Dalia"
    // "Google espanol" -> "espanol"  (con \w se cortaba en la n con tilde)
    const m = v.name.match(/(?:Microsoft|Google)\s+([\p{L}]+)/u);
    if (m) return m[1];
    const primera = v.name.split(/[\s(,-]/).filter(Boolean)[0];
    return primera || v.name;
  }

  function pintarEstado() {
    let voz;
    if (fishAnunciado && !fishComprobado) voz = " · preparando voz";
    else if (fishComprobado) voz = " · voz Fish Audio";
    else if (vozElegida) voz = ` · voz ${nombreCorto(vozElegida)}`;
    else voz = " · voz del navegador";
    const motor = conIA ? "" : " · modo corpus";
    estado.innerHTML = `<b>${normasCargadas}</b> normas cargadas${motor}${voz}`;
  }

  const selVoz = $("#selvoz");

  function poblarSelector(voces) {
    if (!selVoz) return;
    const guardada = (() => {
      try { return localStorage.getItem("lexian.voz"); } catch { return null; }
    })();
    selVoz.innerHTML = "";
    voces.forEach((v, i) => {
      const op = document.createElement("option");
      op.value = v.name;
      // Marcamos cuales son las neurales: son las que suenan a persona.
      const natural = /natural|online/i.test(v.name) ? "  ★ natural" : "";
      op.textContent = `${nombreCorto(v)} (${v.lang})${natural}`;
      selVoz.appendChild(op);
      if (guardada === v.name) selVoz.selectedIndex = i;
    });
    if (guardada && voces.some((v) => v.name === guardada)) {
      vozElegida = voces.find((v) => v.name === guardada);
    } else if (vozElegida) {
      selVoz.value = vozElegida.name;
    }
  }

  if (selVoz) {
    selVoz.addEventListener("change", () => {
      const voces = speechSynthesis.getVoices();
      vozElegida = voces.find((v) => v.name === selVoz.value) || vozElegida;
      try { localStorage.setItem("lexian.voz", selVoz.value); } catch {}
      pintarEstado();
      // Se prueba al instante, para no tener que adivinar como suena.
      speechSynthesis.cancel();
      const demo = new SpeechSynthesisUtterance("Soy Lexian, tu asesor laboral.");
      demo.voice = vozElegida;
      demo.lang = vozElegida ? vozElegida.lang : "es-ES";
      demo.rate = 1.02;
      demo.pitch = 0.95;
      speechSynthesis.speak(demo);
    });
  }

  function elegirVoz() {
    if (!("speechSynthesis" in window)) return;
    const voces = speechSynthesis.getVoices();
    if (!voces.length) return;

    const espanol = voces.filter((v) => /^es(-|_|$)/i.test(v.lang));
    if (!espanol.length) return;

    // Orden de preferencia. Lo primero son las voces NEURALES que Microsoft
    // Edge expone como "Online (Natural)": son gratuitas y suenan a persona,
    // no a sintetizador de los noventa.
    // Lexian es un hombre: buscamos voz masculina en espanol, y dentro de
    // esas, primero las neurales de Edge ("Online (Natural)"), que suenan a
    // persona de verdad.
    const MASCULINAS = /gonzalo|alvaro|[aá]lvaro|jorge|pablo|raul|ra[uú]l|dalia_no|liberto|elias|el[ií]as|luciano|male|masculin/i;

    const preferidas = [
      (v) => MASCULINAS.test(v.name) && /natural|online/i.test(v.name), // neural masculina
      (v) => MASCULINAS.test(v.name),                                   // masculina clasica
      (v) => /natural|online/i.test(v.name),                            // neural cualquiera
      (v) => /google.*espa|espa.*google/i.test(v.name),                 // Chrome
      (v) => /es-(CO|MX|US|AR)/i.test(v.lang),                          // latinoamericana
    ];
    for (const cumple of preferidas) {
      const hallada = espanol.find(cumple);
      if (hallada) {
        vozElegida = hallada;
        return;
      }
    }
    vozElegida = espanol[0];
  }

  function ordenarYPoblar() {
    if (!("speechSynthesis" in window)) return;
    const espanol = speechSynthesis
      .getVoices()
      .filter((v) => /^es(-|_|$)/i.test(v.lang))
      // Las neurales primero: son las que suenan bien.
      .sort((a, b) => /natural|online/i.test(b.name) - /natural|online/i.test(a.name));
    if (espanol.length) poblarSelector(espanol);
  }

  elegirVoz();
  ordenarYPoblar();
  if ("speechSynthesis" in window) {
    speechSynthesis.addEventListener("voiceschanged", () => {
      elegirVoz();
      ordenarYPoblar();
      pintarEstado();
    });
  }

  function hablarConNavegador(texto) {
    // Segunda opcion: sintesis de voz del propio navegador. Es gratuita, no
    // necesita ninguna llave y FUNCIONA SIN INTERNET. Si tampoco esta
    // disponible, caemos a subtitulos temporizados.
    if (!("speechSynthesis" in window)) return false;
    try {
      speechSynthesis.cancel();
      if (!vozElegida) elegirVoz();

      const frase = new SpeechSynthesisUtterance(texto);
      frase.lang = vozElegida ? vozElegida.lang : "es-ES";
      frase.rate = 1.02;   // ritmo de conversacion, no de locutor
      frase.pitch = 0.95;
      frase.volume = 1;
      if (vozElegida) frase.voice = vozElegida;

      const duracion = Math.max(2600, (texto.length / 13) * 1000);
      frase.onstart = () => {
        Avatar.hablar(true);
        mostrarSubtitulos(texto, duracion);
      };
      // Cada palabra pronunciada da un golpe de apertura a la boca.
      frase.onboundary = () => {
        Avatar.nivel = 0.55 + Math.random() * 0.45;
      };
      frase.onend = () => Avatar.hablar(false);

      speechSynthesis.speak(frase);
      return true;
    } catch {
      return false;
    }
  }

  function hablarSinAudio(texto) {
    // Orden de preferencia: Fish Audio (mejor voz) -> voz del navegador
    // (gratis y sin internet) -> subtitulos temporizados.
    if (hablarConNavegador(texto)) return;
    const duracion = Math.max(2600, (texto.length / 14) * 1000);
    Avatar.hablar(true);
    Avatar.gesto("explicar");
    mostrarSubtitulos(texto, duracion);
  }

  async function hablar(texto, fueraDeDominio) {
    if (!texto) return;
    if (audioActual) {
      audioActual.pause();
      audioActual = null;
    }
    Avatar.gesto(fueraDeDominio ? "negar" : "explicar");

    let respuesta;
    try {
      respuesta = await fetch("/api/voz", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto: texto.slice(0, 1200) }),
      });
    } catch {
      return hablarSinAudio(texto);
    }
    if (respuesta.status !== 200) {
      // Fish Audio no devolvio audio (sin credito, sin llave o sin red):
      // se corrige el indicador en vez de seguir anunciando algo que no pasa.
      fishAnunciado = false;
      pintarEstado();
      return hablarSinAudio(texto);
    }
    fishComprobado = true;
    pintarEstado();

    const url = URL.createObjectURL(await respuesta.blob());
    const audio = new Audio(url);
    audioActual = audio;

    // El volumen instantaneo del audio mueve la mandibula: asi el movimiento de
    // la boca coincide de verdad con lo que se escucha.
    try {
      contextoAudio = contextoAudio || new (AudioContext || webkitAudioContext)();
      if (contextoAudio.state === "suspended") await contextoAudio.resume();
      const fuente = contextoAudio.createMediaElementSource(audio);
      const analizador = contextoAudio.createAnalyser();
      analizador.fftSize = 256;
      fuente.connect(analizador);
      analizador.connect(contextoAudio.destination);
      const datos = new Uint8Array(analizador.frequencyBinCount);

      (function medir() {
        if (audio.paused || audio.ended) {
          Avatar.nivel = 0;
          return;
        }
        analizador.getByteTimeDomainData(datos);
        let suma = 0;
        for (let i = 0; i < datos.length; i++) {
          const v = (datos[i] - 128) / 128;
          suma += v * v;
        }
        Avatar.nivel = Math.min(1, Math.sqrt(suma / datos.length) * 5.5);
        requestAnimationFrame(medir);
      })();
    } catch {
      /* Sin WebAudio la boca usa la oscilacion por defecto. */
    }

    audio.addEventListener("loadedmetadata", () => {
      const ms = isFinite(audio.duration) ? audio.duration * 1000 : (texto.length / 14) * 1000;
      Avatar.hablar(true);
      mostrarSubtitulos(texto, ms);
    });
    audio.addEventListener("ended", () => {
      Avatar.hablar(false);
      URL.revokeObjectURL(url);
    });

    audio.play().catch(() => hablarSinAudio(texto));
  }

  /* ---------------- Dibujado de la respuesta ---------------- */
  const escapar = (t) =>
    String(t == null ? "" : t).replace(/[&<>"]/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])
    );

  function agregar(html) {
    const div = document.createElement("div");
    div.innerHTML = html;
    conversacion.appendChild(div);
    conversacion.scrollTop = conversacion.scrollHeight;
    return div;
  }

  function dibujarRespuesta(d) {
    // Un saludo o un mensaje incompleto se responden con una tarjeta neutra:
    // usar la de alerta haria parecer que el usuario hizo algo mal.
    if (d.saludo) {
      return `
        <article class="tarjeta">
          <h3>Soy Lexian</h3>
          <p>${escapar(d.resumen)}</p>
          ${
            d.pasos && d.pasos.length
              ? `<ol class="pasos">${d.pasos.map((p) => `<li>${escapar(p)}</li>`).join("")}</ol>`
              : ""
          }
        </article>`;
    }

    if (d.fuera_de_dominio) {
      return `
        <article class="tarjeta fuera">
          <h3>Fuera de mi especialidad</h3>
          <p>${escapar(d.resumen)}</p>
          ${
            d.pasos && d.pasos.length
              ? `<h3 style="margin-top:14px">A donde acudir</h3>
                 <ol class="pasos">${d.pasos.map((p) => `<li>${escapar(p)}</li>`).join("")}</ol>`
              : ""
          }
        </article>`;
    }

    const normas = (d.normas || [])
      .map(
        (n) => `
        <div class="norma">
          <div class="cita">${escapar(n.cita)}</div>
          <div class="porque">${escapar(n.por_que)}</div>
          ${n.fragmento ? `<blockquote>${escapar(n.fragmento)}</blockquote>` : ""}
          ${
            n.fuente
              ? `<a href="${escapar(n.fuente)}" target="_blank" rel="noopener">Ver la norma oficial &rarr;</a>`
              : ""
          }
        </div>`
      )
      .join("");

    return `
      <article class="tarjeta">
        <h3>Tu situacion</h3>
        <p>${escapar(d.resumen)}</p>
        <span class="confianza" data-nivel="${escapar(d.confianza)}">Confianza ${escapar(d.confianza)}</span>
      </article>
      ${normas ? `<article class="tarjeta"><h3>Normas que te respaldan</h3>${normas}</article>` : ""}
      ${
        d.pasos && d.pasos.length
          ? `<article class="tarjeta"><h3>Que puedes hacer ahora</h3>
             <ol class="pasos">${d.pasos.map((p) => `<li>${escapar(p)}</li>`).join("")}</ol></article>`
          : ""
      }`;
  }

  /* ---------------- Envio ---------------- */
  async function consultar(texto) {
    if (ocupado) return;
    texto = texto.trim();
    if (!texto) {
      campo.focus();
      return;
    }

    ocupado = true;
    boton.disabled = true;
    boton.textContent = "Consultando...";
    limpiarTemporizadores();
    if ("speechSynthesis" in window) speechSynthesis.cancel();
    subtitulos.classList.add("oculto");
    Avatar.hablar(false);

    const vacio = $("#vacio");
    if (vacio) vacio.remove();

    agregar(`<div class="burbuja-usuario">${escapar(texto)}</div>`);
    const espera = agregar(
      '<div class="tarjeta"><h3>Revisando la normativa</h3><div class="puntos"><span></span><span></span><span></span></div></div>'
    );

    try {
      const r = await fetch("/api/consulta", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto }),
      });
      const datos = await r.json();

      if (!r.ok) {
        espera.innerHTML = `<article class="tarjeta fallo"><h3>No pude responder</h3><p>${escapar(
          datos.detail || "Error inesperado."
        )}</p></article>`;
      } else {
        espera.innerHTML = dibujarRespuesta(datos);
        hablar(datos.mensaje_hablado || datos.resumen, datos.fuera_de_dominio);
      }
    } catch {
      espera.innerHTML =
        '<article class="tarjeta fallo"><h3>Sin conexion</h3><p>No pude comunicarme con el servidor. Comprueba que la aplicacion siga corriendo.</p></article>';
    } finally {
      ocupado = false;
      boton.disabled = false;
      boton.textContent = "Consultar";
      conversacion.scrollTop = conversacion.scrollHeight;
      campo.focus();
    }
  }

  formulario.addEventListener("submit", (e) => {
    e.preventDefault();
    const t = campo.value;
    campo.value = "";
    campo.style.height = "auto";
    consultar(t);
  });

  // Enter envia, Shift+Enter hace salto de linea.
  campo.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      formulario.requestSubmit();
    }
  });

  campo.addEventListener("input", () => {
    campo.style.height = "auto";
    campo.style.height = Math.min(campo.scrollHeight, 150) + "px";
  });

  document.addEventListener("click", (e) => {
    const ejemplo = e.target.closest(".ejemplo");
    if (ejemplo) consultar(ejemplo.textContent);
  });

  campo.focus();
})();
