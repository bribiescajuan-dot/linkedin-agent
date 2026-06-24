# 🎯 Agente de Prospección LinkedIn

Agente inteligente para buscar empresas y contactos usando información pública. Powered by Claude AI.

## 🚀 Deploy en Render (Paso a Paso)

### 1. Sube el código a GitHub

1. Ve a **github.com** y crea un nuevo repositorio llamado `linkedin-agent`
2. Descarga estos archivos y súbelos al repositorio
   - O usa GitHub Desktop si no sabes usar git

### 2. Configura Render

1. Ve a **render.com** e inicia sesión con GitHub
2. Click en **"New +"** → **"Web Service"**
3. Conecta tu repositorio `linkedin-agent`
4. Configura así:
   - **Name:** `linkedin-agent`
   - **Environment:** `Docker`
   - **Region:** `Oregon (US West)` o la más cercana
   - **Instance Type:** `Free`

### 3. Variables de entorno

En Render, antes de hacer deploy, agrega esta variable:

| Key | Value |
|-----|-------|
| `ANTHROPIC_API_KEY` | `sk-ant-tu-key-aqui` |

### 4. Deploy

Click en **"Create Web Service"** y espera 5-10 minutos.

Render te dará un link como: `https://linkedin-agent-xxxx.onrender.com`

---

## 💬 Cómo usarlo

Abre tu link y escribe en el chat:

- `"Busca 10 empresas de mensajería en México"`
- `"Encuentra al Director de Operaciones en empresas de logística en CDMX"`
- `"Busca empresas de tecnología en Monterrey con 50-200 empleados"`

---

## 📁 Estructura del proyecto

```
linkedin-agent/
├── main.py          ← Servidor FastAPI
├── agent.py         ← Cerebro (Claude API)
├── scraper.py       ← Playwright busca en web
├── index.html       ← Interfaz de chat
├── requirements.txt ← Dependencias Python
├── Dockerfile       ← Para Render/Railway
└── README.md        ← Este archivo
```

## ⚠️ Notas importantes

- El agente usa **información pública** de LinkedIn y Google
- No requiere login en LinkedIn (Agente A gratuito)
- Los resultados dependen de lo que LinkedIn muestra sin login
- Para datos más completos (emails directos, teléfonos) → Agente B (próximamente)

## 🔧 Correr localmente (opcional)

```bash
pip install -r requirements.txt
playwright install chromium
export ANTHROPIC_API_KEY=sk-ant-tu-key
python main.py
```

Abre: http://localhost:8000
