# Asesor Laboral de Bolsillo

**Equipo Mondagascar**

Orientación clara sobre **derecho laboral colombiano** para quien no puede pagar un
abogado. Escribes lo que te pasó con tus palabras y recibes: qué dice la ley, los
artículos exactos que te respaldan con su texto a la vista, y los pasos concretos
que puedes dar.

La respuesta la da **Lexian**: te habla en voz alta mientras un visualizador
reacciona a su voz y todo queda subtitulado en pantalla. Sin jerga jurídica.

---

## El problema

Una persona a la que despidieron o a la que su jefe humilla en el trabajo no sabe
dos cosas: si lo que le pasó tiene respaldo legal, y qué puede hacer al respecto.
Una consulta con un abogado cuesta más de lo que esa persona tiene. Y buscar en
internet devuelve blogs desactualizados, publicidad de firmas jurídicas y foros
donde cualquiera opina.

## La solución

Un asesor acotado a **un solo dominio** —derecho laboral colombiano— que solo
puede responder citando un corpus normativo real incluido en este repositorio.
No responde de memoria. Si tu caso no es laboral, te lo dice y te manda a la
entidad correcta, en vez de inventarte una norma.

---

## Cómo ejecutarlo

### Requisitos
- **Python 3.10 o superior** (`python --version` para comprobarlo)
- Una llave de la API de Anthropic (opcional — sin ella la app funciona igual, ver abajo)

### Opción A — arranque con un solo comando

**Windows** (PowerShell o CMD, dentro de la carpeta del proyecto):
```
.\iniciar.bat
```

**Linux / macOS:**
```
chmod +x iniciar.sh
./iniciar.sh
```

Crea el entorno virtual, instala las dependencias y abre la aplicación.

### Opción B — paso a paso

```bash
# 1. Clonar y entrar
git clone <URL-DE-ESTE-REPOSITORIO>
cd asesor-laboral

# 2. Entorno virtual
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux / macOS

# 3. Dependencias
pip install -r requirements.txt

# 4. Variables de entorno
copy .env.example .env       # Windows
cp .env.example .env         # Linux / macOS
#    ...y abre .env para poner tu ANTHROPIC_API_KEY (opcional)

# 5. Arrancar
python run.py
```

La aplicación queda en **http://127.0.0.1:8000** y se abre sola en el navegador.

---

## Variables de entorno

| Variable | ¿Obligatoria? | Cómo obtenerla |
|---|---|---|
| `ANTHROPIC_API_KEY` | No | Con ella las respuestas las redacta Claude y suenan naturales. **Sin ella la aplicación sigue funcionando**: responde directamente desde el corpus, citando los mismos artículos. Se obtiene en **https://console.anthropic.com** → *API Keys*. |
| `CLAUDE_MODEL` | No | Por defecto `claude-opus-5`. |
| `FISH_API_KEY` | No | Voz de alta calidad. Sin ella se usa la voz del navegador, que es gratuita y funciona sin internet. Se obtiene en **https://fish.audio** → *API Keys*. |
| `FISH_VOICE_ID` | No | Identificador de la voz elegida en Fish Audio. |

**Ninguna variable es obligatoria.** La aplicación arranca y responde sin ninguna
llave: usa el corpus directamente y la voz del navegador. Se diseñó así a propósito
para que nunca falle al ejecutarse en una máquina ajena.

Las llaves reales **nunca** están en el repositorio: `.env` está en `.gitignore`.

---

## Arquitectura

```
                    Navegador
   ┌───────────────────────────────────────────┐
   │  Visualizador de voz (canvas 2D, 6 KB,    │
   │  sin librerias ni archivos externos)      │
   │  + subtítulos + panel de conversación     │
   └───────────────────┬───────────────────────┘
                       │  POST /api/consulta
                       ▼
            FastAPI  (un solo proceso sirve
            la interfaz Y la API, sin CORS)
                       │
        ┌──────────────┼──────────────────┐
        ▼              ▼                  ▼
   app/rag.py     app/llm.py          app/db.py
   BM25 sobre     Claude redacta      SQLite:
   /corpus        SOLO con los        historial que
   (29 normas)    fragmentos          sobrevive al
                  recuperados         reinicio
                  (+ modo sin
                   conexion)
                       │
                       ▼
                 POST /api/voz
                 Fish Audio  ──► audio ──► analizador de
                 (o voz del               volumen que anima
                  navegador)              el visualizador
```

### Por qué estas decisiones

**Python + FastAPI y una página HTML sin compilar.** La prueba que más pesa es que
la aplicación arranque en una máquina limpia. Cada paso de compilación es una
forma más de fallar. Aquí no hay `npm install`, ni empaquetador, ni build.

**BM25 en lugar de embeddings.** Con 29 documentos la búsqueda léxica es igual de
precisa, no consume cuota de ninguna API, no descarga modelos y funciona sin
conexión. Menos piezas, menos cosas que se rompan.

**El modelo no puede responder de memoria.** Recibe los fragmentos recuperados y
la instrucción explícita de no citar nada que no esté en ellos. Por eso las citas
son verificables: el fragmento que ves en pantalla es exactamente el que se le
entregó al modelo.

**El visualizador de voz es un canvas 2D de 6 KB.** Nada de WebGL, modelos 3D ni
librerías: un núcleo que se deforma con el volumen real de la voz, ondas que se
expanden mientras habla y un espectro debajo. El color cambia a ámbar cuando la
respuesta es "esto no es de mi competencia", así que se entiende el tipo de
respuesta antes de leer una sola palabra. Carga instantánea y funciona sin
internet.

**La detección de casos fuera de dominio es determinista antes que probabilística.**
Si BM25 no encuentra ninguna norma con puntaje positivo, ya sabemos que el caso no
es laboral sin siquiera llamar al modelo. El modelo es la segunda barrera, no la
primera.

---

## Flujo de uso

1. Al abrir, Lexian se presenta y el panel derecho propone tres casos de ejemplo.
2. Escribes tu situación en lenguaje natural (o pulsas un ejemplo).
3. Mientras busca, aparece el estado *"Revisando la normativa"*.
4. La respuesta llega en tres bloques:
   - **Tu situación** — el caso en términos legales, con un indicador de confianza.
   - **Normas que te respaldan** — cada una con su cita, por qué aplica a tu caso,
     el fragmento textual y un enlace a la fuente oficial.
   - **Qué puedes hacer ahora** — pasos accionables.
5. A la vez, Lexian lo explica en voz alta con subtítulos sincronizados.
6. Si el caso no es laboral, lo dice y te indica a qué entidad acudir.

---

## Corpus normativo

29 documentos en `/corpus`, cada uno con su norma, artículo, tema y **enlace a la
fuente oficial** (Secretaría del Senado y SUIN-Juriscol):

| Norma | Tema |
|---|---|
| CST art. 64 | Indemnización por despido sin justa causa |
| CST art. 65 | Sanción moratoria por no pagar la liquidación |
| CST art. 62 | Justas causas de terminación (y despido indirecto) |
| CST art. 249 | Auxilio de cesantía |
| Ley 52 de 1975 | Intereses sobre las cesantías |
| CST art. 306 | Prima de servicios |
| CST art. 186 | Vacaciones |
| CST art. 57 | Obligaciones del empleador y dignidad del trabajador |
| CST art. 488 | Prescripción: plazo para reclamar |
| Ley 1010 de 2006, art. 2 | Definición y modalidades de acoso laboral |
| Ley 1010 de 2006, art. 7 | Conductas que constituyen acoso laboral |
| Ley 1010 de 2006, art. 9 | Cómo y dónde denunciar el acoso |
| CST art. 239 | Fuero de maternidad: prohibición de despido por embarazo |
| CST art. 236 | Licencia de maternidad (18 semanas) y de paternidad |
| CST art. 168 | Recargo nocturno y horas extras (25%, 35%, 75%) |
| CST art. 179 | Trabajo en domingos y festivos (75%) |
| Ley 2101 de 2021 | Jornada máxima: 42 horas semanales desde julio de 2026 |
| Ley 1562 de 2012 | Accidente de trabajo y ARL |
| CST art. 23 y 24 | Contrato realidad: primacía de la realidad sobre la forma |
| CST art. 76-80 | Periodo de prueba |
| CST art. 46 | Contrato a término fijo y su renovación |
| CST art. 230 | Dotación: calzado y vestido de labor |
| CST art. 132 | Salario integral y formas de salario |
| Ley 1280 de 2009 | Licencia por luto (5 días hábiles) |
| Ley 361 de 1997 | Estabilidad laboral reforzada por salud |
| Ley 100 de 1993 | Aportes a salud, pensión y riesgos laborales |
| Ley 1788 de 2016 | Derechos del servicio doméstico |
| Ley 789 de 2002 | Contrato de aprendizaje (SENA) |
| Ley 1221 de 2008 | Teletrabajo y derecho a la desconexión |

---

## Set de evaluación

`eval_cases.json` contiene 6 casos con su respuesta esperada, incluidos dos fuera
de dominio. Para ejecutarlos:

```bash
python evaluar.py
```

Comprueba, caso por caso, si la aplicación acierta al declarar el dominio y si
cita las normas que debería citar.

---

## Responsabilidad y límites

- **Aviso legal visible y permanente** en la parte superior de la pantalla. No se
  puede cerrar.
- **No inventa normas.** Solo cita lo que está en el corpus. Si no encuentra nada
  aplicable, lo declara con confianza *baja*.
- **Reconoce lo que no sabe.** Ante un caso civil, penal, de consumidor o de
  familia, lo dice y remite a la entidad competente.
- **No pide datos sensibles.** Ni cédula, ni teléfono, ni dirección, ni correo.
  Está escrito en la interfaz y en las instrucciones del modelo.

---

## Estructura del proyecto

```
asesor-laboral/
├── app/
│   ├── main.py        API y servidor
│   ├── rag.py         Índice BM25 sobre el corpus
│   ├── llm.py         Prompt y llamada al modelo
│   └── db.py          Historial en SQLite
├── corpus/            29 normas con su fuente oficial
├── static/
│   ├── index.html     Interfaz
│   ├── voz.js         Visualizador de voz (canvas 2D)
│   └── app.js         Conversación, voz y subtítulos
├── data/              Base de datos del historial (no se versiona)
├── eval_cases.json    Set de evaluación
├── evaluar.py         Ejecuta el set de evaluación
├── requirements.txt   Dependencias con versiones fijas
├── .env.example       Plantilla de variables de entorno
├── run.py             Arranque
├── iniciar.bat          Arranque de un comando (Windows)
└── iniciar.sh           Arranque de un comando (Linux / macOS)
```

---

## Accesibilidad

- Navegación completa por teclado; `Enter` envía y `Shift+Enter` hace salto de línea.
- Regiones `aria-live` para el estado y los subtítulos.
- Etiquetas descriptivas en los controles de formulario.
- Contraste alto en todo el texto.
- Respeta `prefers-reduced-motion`.
- Si el navegador no soporta canvas, la asesoría funciona igual sin el visualizador.
