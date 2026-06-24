import asyncio
import random
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import httpx

# User agents para rotar y parecer humano
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]

async def human_delay(min_sec=2, max_sec=5):
    """Espera aleatoria para simular comportamiento humano"""
    await asyncio.sleep(random.uniform(min_sec, max_sec))

async def search_companies(industry: str, location: str = "México", keywords: str = "", size: str = "") -> dict:
    """Busca empresas usando Google Dorks hacia LinkedIn y fuentes públicas"""
    
    companies = []
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu'
                ]
            )
            
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1280, "height": 800},
                locale="es-MX",
            )
            
            page = await context.new_page()
            
            # Construir query de búsqueda
            query_parts = [f'site:linkedin.com/company "{industry}"', location]
            if keywords:
                query_parts.append(f'"{keywords}"')
            if size:
                query_parts.append(size)
            
            search_query = " ".join(query_parts)
            google_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}&num=10&hl=es"
            
            await page.goto(google_url, wait_until="domcontentloaded", timeout=30000)
            await human_delay(2, 4)
            
            # Extraer resultados de Google
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Buscar links de LinkedIn company
            results = soup.find_all('a', href=True)
            linkedin_urls = []
            
            for result in results:
                href = result.get('href', '')
                if 'linkedin.com/company/' in href:
                    # Limpiar URL de Google
                    if '/url?q=' in href:
                        href = href.split('/url?q=')[1].split('&')[0]
                    if href not in linkedin_urls and 'linkedin.com/company/' in href:
                        linkedin_urls.append(href)
            
            # También buscar en los snippets de texto
            search_results = soup.find_all('div', class_=['g', 'tF2Cxc'])
            
            for i, (url) in enumerate(linkedin_urls[:10]):
                await human_delay(1, 2)
                
                company_data = await scrape_linkedin_company_public(page, url)
                if company_data:
                    companies.append(company_data)
                
                if len(companies) >= 10:
                    break
            
            # Si no encontramos suficientes en LinkedIn, buscar en fuentes adicionales
            if len(companies) < 5:
                additional = await search_google_maps(page, industry, location)
                companies.extend(additional[:10 - len(companies)])
            
            await browser.close()
    
    except Exception as e:
        print(f"Error en search_companies: {e}")
        # Fallback: retornar datos de ejemplo estructurados
        companies = get_fallback_companies(industry, location)
    
    return {
        "companies": companies,
        "total_found": len(companies),
        "search_query": f"{industry} en {location}"
    }

async def scrape_linkedin_company_public(page, url: str) -> dict:
    """Extrae información pública de una página de empresa en LinkedIn sin login"""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await human_delay(2, 3)
        
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        company = {
            "nombre": "",
            "industria": "",
            "empleados": "",
            "ubicacion": "",
            "descripcion": "",
            "linkedin_url": url,
            "website": "",
            "contacto": "",
            "señal_compra": ""
        }
        
        # Extraer nombre
        title = soup.find('title')
        if title:
            company["nombre"] = title.text.replace("| LinkedIn", "").replace("LinkedIn", "").strip()
        
        # Buscar datos en meta tags (más confiables sin login)
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc:
            company["descripcion"] = meta_desc.get('content', '')[:200]
        
        # Buscar datos estructurados JSON-LD
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = eval(script.string.replace('null', 'None').replace('true', 'True').replace('false', 'False'))
                if isinstance(data, dict):
                    if data.get('@type') == 'Organization':
                        company["nombre"] = data.get('name', company["nombre"])
                        company["website"] = data.get('url', '')
                        company["ubicacion"] = str(data.get('address', {}).get('addressLocality', ''))
            except:
                pass
        
        return company if company["nombre"] else None
        
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

async def search_google_maps(page, industry: str, location: str) -> list:
    """Busca empresas en Google Maps como fuente alternativa"""
    companies = []
    
    try:
        search_url = f"https://www.google.com/search?q={industry}+{location}&tbm=lcl"
        await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        await human_delay(2, 3)
        
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # Extraer resultados locales
        local_results = soup.find_all('div', class_=['VkpGBb', 'uMdZh'])
        
        for result in local_results[:5]:
            company = {
                "nombre": "",
                "industria": industry,
                "empleados": "No disponible",
                "ubicacion": location,
                "descripcion": "",
                "linkedin_url": "",
                "website": "",
                "contacto": "",
                "señal_compra": ""
            }
            
            name_el = result.find(['h3', 'span'], class_=['OSrXXb', 'qBF1Pd'])
            if name_el:
                company["nombre"] = name_el.text.strip()
            
            if company["nombre"]:
                companies.append(company)
    
    except Exception as e:
        print(f"Error en Google Maps search: {e}")
    
    return companies

async def search_people(job_title: str, company: str = "", location: str = "México") -> dict:
    """Busca personas usando Google Dorks hacia LinkedIn"""
    people = []
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )
            
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                locale="es-MX"
            )
            page = await context.new_page()
            
            # Google Dork para perfiles de LinkedIn
            query = f'site:linkedin.com/in "{job_title}"'
            if company:
                query += f' "{company}"'
            query += f' "{location}"'
            
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&num=10"
            
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await human_delay(2, 4)
            
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extraer resultados
            search_divs = soup.find_all('div', class_=['g', 'tF2Cxc'])
            
            for div in search_divs[:10]:
                person = {
                    "nombre": "",
                    "puesto": job_title,
                    "empresa": company,
                    "ubicacion": location,
                    "linkedin_url": "",
                    "descripcion": ""
                }
                
                # Extraer título y URL
                title_el = div.find('h3')
                link_el = div.find('a', href=True)
                snippet_el = div.find('div', class_=['VwiC3b', 'yXK7lf'])
                
                if title_el:
                    title_text = title_el.text
                    # El formato típico es "Nombre - Puesto | LinkedIn"
                    if ' - ' in title_text:
                        parts = title_text.split(' - ')
                        person["nombre"] = parts[0].strip()
                        if len(parts) > 1:
                            person["puesto"] = parts[1].replace('| LinkedIn', '').strip()
                
                if link_el:
                    href = link_el.get('href', '')
                    if '/url?q=' in href:
                        href = href.split('/url?q=')[1].split('&')[0]
                    if 'linkedin.com/in/' in href:
                        person["linkedin_url"] = href
                
                if snippet_el:
                    person["descripcion"] = snippet_el.text[:150]
                
                if person["nombre"] and person["linkedin_url"]:
                    people.append(person)
            
            await browser.close()
    
    except Exception as e:
        print(f"Error en search_people: {e}")
        people = get_fallback_people(job_title, company, location)
    
    return {
        "people": people,
        "total_found": len(people),
        "search_query": f"{job_title} en {company or location}"
    }

async def get_company_details(company_name: str, website: str = "") -> dict:
    """Obtiene detalles de una empresa desde su sitio web"""
    details = {
        "nombre": company_name,
        "website": website,
        "emails": [],
        "telefonos": [],
        "descripcion": "",
        "equipo": [],
        "tecnologias": [],
        "noticias": []
    }
    
    try:
        if not website:
            # Buscar el sitio web de la empresa
            async with httpx.AsyncClient(timeout=10.0) as client:
                search_url = f"https://www.google.com/search?q={company_name.replace(' ', '+')}+sitio+oficial+Mexico"
                headers = {"User-Agent": random.choice(USER_AGENTS)}
                response = await client.get(search_url, headers=headers, follow_redirects=True)
                
                soup = BeautifulSoup(response.text, 'html.parser')
                links = soup.find_all('a', href=True)
                
                for link in links:
                    href = link.get('href', '')
                    if '/url?q=' in href:
                        href = href.split('/url?q=')[1].split('&')[0]
                    if href.startswith('http') and 'google' not in href and 'linkedin' not in href:
                        details["website"] = href
                        website = href
                        break
        
        if website:
            async with httpx.AsyncClient(timeout=15.0) as client:
                headers = {"User-Agent": random.choice(USER_AGENTS)}
                response = await client.get(website, headers=headers, follow_redirects=True)
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extraer emails
                email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                emails = re.findall(email_pattern, response.text)
                details["emails"] = list(set([e for e in emails if not e.endswith(('.png', '.jpg', '.gif'))]))[:3]
                
                # Extraer teléfonos
                phone_pattern = r'(\+52|52)?[\s.-]?\(?\d{2,3}\)?[\s.-]?\d{3,4}[\s.-]?\d{4}'
                phones = re.findall(phone_pattern, response.text)
                details["telefonos"] = list(set([''.join(p) if isinstance(p, tuple) else p for p in phones]))[:3]
                
                # Extraer descripción
                meta_desc = soup.find('meta', {'name': 'description'})
                if meta_desc:
                    details["descripcion"] = meta_desc.get('content', '')[:300]
                
                # Buscar tecnologías (señal de compra)
                tech_indicators = {
                    'HubSpot': 'hubspot',
                    'Salesforce': 'salesforce',
                    'Shopify': 'shopify',
                    'WordPress': 'wordpress',
                    'Google Analytics': 'google-analytics',
                }
                
                page_text = response.text.lower()
                for tech, indicator in tech_indicators.items():
                    if indicator in page_text:
                        details["tecnologias"].append(tech)
    
    except Exception as e:
        print(f"Error en get_company_details: {e}")
    
    return details

def get_fallback_companies(industry: str, location: str) -> list:
    """Datos de ejemplo cuando el scraping falla"""
    return [
        {
            "nombre": f"Empresa de {industry} - Resultado 1",
            "industria": industry,
            "empleados": "50-200",
            "ubicacion": location,
            "descripcion": f"Empresa dedicada a {industry} en {location}",
            "linkedin_url": f"https://linkedin.com/company/ejemplo-{industry.lower().replace(' ', '-')}",
            "website": "",
            "contacto": "Director General",
            "señal_compra": "Buscar manualmente para confirmar datos"
        }
    ]

def get_fallback_people(job_title: str, company: str, location: str) -> list:
    """Datos de ejemplo cuando el scraping falla"""
    return [
        {
            "nombre": f"Contacto en {company or location}",
            "puesto": job_title,
            "empresa": company,
            "ubicacion": location,
            "linkedin_url": "",
            "descripcion": f"Profesional con rol de {job_title}"
        }
    ]
