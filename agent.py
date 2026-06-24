import anthropic
import json
import os
from scraper import search_companies, search_people, get_company_details

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """Eres un agente experto en prospección de clientes B2B para el mercado mexicano y latinoamericano.

Tu trabajo es ayudar a encontrar empresas y contactos potenciales usando información pública disponible en internet.

Cuando el usuario te pida buscar empresas o contactos, debes:
1. Interpretar claramente qué tipo de empresa o persona busca
2. Usar las herramientas disponibles para buscar
3. Analizar los resultados y presentarlos de forma clara
4. Identificar señales de compra cuando sea posible

Responde siempre en español. Sé directo y útil.

Herramientas disponibles:
- search_companies: Busca empresas por industria, ubicación y palabras clave
- search_people: Busca personas por puesto y empresa
- get_company_details: Obtiene detalles de una empresa específica

Formato de respuesta: Presenta los resultados de forma clara con emojis para facilitar la lectura.
Cuando presentes empresas, usa este formato:
🏢 **Nombre de empresa**
📍 Ubicación | 👥 Tamaño
🌐 Sitio web
👤 Contacto: Nombre - Puesto
🚨 Señal: [señal de compra si existe]
---
"""

TOOLS = [
    {
        "name": "search_companies",
        "description": "Busca empresas en LinkedIn y Google por industria, ubicación y palabras clave",
        "input_schema": {
            "type": "object",
            "properties": {
                "industry": {
                    "type": "string",
                    "description": "Industria o giro de la empresa (ej: mensajería, logística, tecnología)"
                },
                "location": {
                    "type": "string", 
                    "description": "País o ciudad (ej: México, CDMX, Monterrey)"
                },
                "keywords": {
                    "type": "string",
                    "description": "Palabras clave adicionales para filtrar"
                },
                "size": {
                    "type": "string",
                    "description": "Tamaño de empresa (ej: pequeña, mediana, grande, 50-200 empleados)"
                }
            },
            "required": ["industry"]
        }
    },
    {
        "name": "search_people",
        "description": "Busca personas por puesto y empresa en LinkedIn",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_title": {
                    "type": "string",
                    "description": "Puesto o cargo (ej: Director de Operaciones, Gerente de Logística, CEO)"
                },
                "company": {
                    "type": "string",
                    "description": "Nombre de la empresa donde buscar"
                },
                "location": {
                    "type": "string",
                    "description": "Ubicación"
                }
            },
            "required": ["job_title"]
        }
    },
    {
        "name": "get_company_details",
        "description": "Obtiene información detallada de una empresa específica",
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "Nombre de la empresa"
                },
                "website": {
                    "type": "string",
                    "description": "Sitio web de la empresa (opcional)"
                }
            },
            "required": ["company_name"]
        }
    }
]

async def run_agent(query: str):
    """Run the agent with streaming responses"""
    
    yield {"type": "status", "message": "🤔 Analizando tu búsqueda..."}
    
    messages = [{"role": "user", "content": query}]
    
    # Agentic loop
    max_iterations = 5
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )
        
        # Check if we need to use tools
        if response.stop_reason == "tool_use":
            # Process tool calls
            tool_results = []
            
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    
                    yield {"type": "status", "message": f"🔍 Buscando {tool_input.get('industry', tool_input.get('job_title', 'información'))}..."}
                    
                    # Execute the tool
                    if tool_name == "search_companies":
                        result = await search_companies(
                            industry=tool_input.get("industry", ""),
                            location=tool_input.get("location", "México"),
                            keywords=tool_input.get("keywords", ""),
                            size=tool_input.get("size", "")
                        )
                    elif tool_name == "search_people":
                        result = await search_people(
                            job_title=tool_input.get("job_title", ""),
                            company=tool_input.get("company", ""),
                            location=tool_input.get("location", "México")
                        )
                    elif tool_name == "get_company_details":
                        result = await get_company_details(
                            company_name=tool_input.get("company_name", ""),
                            website=tool_input.get("website", "")
                        )
                    else:
                        result = {"error": f"Herramienta {tool_name} no encontrada"}
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False)
                    })
            
            # Add assistant response and tool results to messages
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            
        elif response.stop_reason == "end_turn":
            # Extract final text response
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            
            yield {"type": "result", "message": final_text}
            break
    
    if iteration >= max_iterations:
        yield {"type": "error", "message": "Se alcanzó el límite de búsquedas. Por favor intenta una búsqueda más específica."}
