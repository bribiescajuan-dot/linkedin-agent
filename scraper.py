import asyncio
import random
import re
import httpx
from bs4 import BeautifulSoup
import os

HEADERS_LIST = [
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-MX,es;q=0.9",
    }
]

async def human_delay(min_sec=1, max_sec=3):
    await asyncio.sleep(random.uniform(min_sec, max_sec))

async def search_companies(industry: str, location: str = "México", keywords: str = "", size: str = "") -> dict:
    """Busca empresas usando httpx + Google + Google Places"""
    companies = []

    # Fuente 1: Google Search sin navegador
    google_results = await search_google(industry, location, keywords)
    companies.extend(google_results)

    # Fuente 2: Google Places API si hay key
    places_key = os.environ.get("GOOGLE_PLACES_KEY", "")
    if places_key:
        places_results = await search_google_places(industry, location, places_key)
        companies.extend(places_results)

    # Fuente 3: Enriquecer con datos del sitio web
    enriched = []
    for company in companies[:10]:
        if company.get("website"):
            extra = await extract_from_website(company["website"])
            company.update(extra)
        enriched.append(company)

    return {
        "companies": enriched[:10],
        "total_found": len(enriched),
        "search_query": f"{industry} en {location}"
    }

async def search_google(industry: str, location: str, keywords: str = "") -> list:
    """Búsqueda directa en Google sin navegador"""
    companies = []

    try:
        query = f'{industry} empresa {location}'
        if keywords:
            query += f' {keywords}'

        # Búsqueda en Google
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}&num=10&hl=es-419"

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            headers = random.choice(HEADERS_LIST)
            response = await client.get(url, headers=headers)
            await human_delay(1, 2)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Extraer resultados orgánicos
                for result in soup.find_all('div', class_=['g', 'tF2Cxc', 'MjjYud'])[:10]:
                    company = extract_company_from_result(result, industry, location)
                    if company and company.get("nombre"):
                        companies.append(company)

        # Búsqueda adicional en LinkedIn vía Google
        await human_delay(1, 2)
        linkedin_companies = await search_linkedin_via_google(industry, location)
        companies.extend(linkedin_companies)

    except Exception as e:
        print(f"Error en search_google: {e}")

    # Deduplicar por nombre
    seen = set()
    unique = []
    for c in companies:
        name = c.get("nombre", "").lower()
        if name and name not in seen:
            seen.add(name)
            unique.append(c)

    return unique[:10]

async def search_linkedin_via_google(industry: str, location: str) -> list:
    """Busca perfiles de empresas en LinkedIn via Google Dorks"""
    companies = []

    try:
        query = f'site:linkedin.com/company "{industry}" "{location}"'
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}&num=10&hl=es"

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            headers = random.choice(HEADERS_LIST)
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                for result in soup.find_all('div', class_=['g', 'tF2Cxc'])[:8]:
                    title_el = result.find('h3')
                    link_el = result.find('a', href=True)
                    snippet_el = result.find(['div', 'span'], class_=['VwiC3b', 'yXK7lf', 'st'])

                    if title_el and link_el:
                        href = link_el.get('href', '')
                        if '/url?q=' in href:
                            href = href.split('/url?q=')[1].split('&')[0]

                        if 'linkedin.com/company/' in href:
                            name = title_el.text.replace('| LinkedIn', '').replace('- LinkedIn', '').strip()
                            name = name.split('|')[0].split('-')[0].strip()

                            company = {
                                "nombre": name,
                                "industria": industry,
                                "empleados": "Ver en LinkedIn",
                                "ubicacion": location,
                                "descripcion": snippet_el.text[:200] if snippet_el else "",
                                "linkedin_url": href,
                                "website": "",
                                "contacto": "",
                                "señal_compra": ""
                            }
                            companies.append(company)

    except Exception as e:
        print(f"Error en LinkedIn search: {e}")

    return companies

def extract_company_from_result(result, industry: str, location: str) -> dict:
    """Extrae datos de empresa de un resultado de Google"""
    try:
        title_el = result.find('h3')
        link_el = result.find('a', href=True)
        snippet_el = result.find(['div', 'span'], class_=['VwiC3b', 'yXK7lf', 'IsZvec'])

        if not title_el:
            return None

        href = ""
        if link_el:
            href = link_el.get('href', '')
            if '/url?q=' in href:
                href = href.split('/url?q=')[1].split('&')[0]
            # Filtrar URLs no relevantes
            skip_domains = ['google.com', 'youtube.com', 'facebook.com', 'wikipedia.org', 'indeed.com']
            if any(domain in href for domain in skip_domains):
                return None

        return {
            "nombre": title_el.text.strip()[:60],
            "industria": industry,
            "empleados": "",
            "ubicacion": location,
            "descripcion": snippet_el.text[:200] if snippet_el else "",
            "linkedin_url": href if 'linkedin.com' in href else "",
            "website": href if 'linkedin.com' not in href and href.startswith('http') else "",
            "contacto": "",
            "señal_compra": ""
        }
    except:
        return None

async def search_google_places(industry: str, location: str, api_key: str) -> list:
    """Busca en Google Places API (si hay key disponible)"""
    companies = []

    try:
        query = f"{industry} en {location}"
        url = f"https://maps.googleapis.com/maps/api/place/textsearch/json"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params={
                "query": query,
                "language": "es",
                "key": api_key
            })

            data = response.json()

            for place in data.get("results", [])[:10]:
                company = {
                    "nombre": place.get("name", ""),
                    "industria": industry,
                    "empleados": "",
                    "ubicacion": place.get("formatted_address", location),
                    "descripcion": f"Calificación: {place.get('rating', 'N/A')} ⭐",
                    "linkedin_url": "",
                    "website": "",
                    "contacto": "",
                    "señal_compra": "Activo en Google Maps"
                }

                # Obtener detalles adicionales
                place_id = place.get("place_id")
                if place_id:
                    details = await get_place_details(client, place_id, api_key)
                    company.update(details)

                companies.append(company)

    except Exception as e:
        print(f"Error en Google Places: {e}")

    return companies

async def get_place_details(client, place_id: str, api_key: str) -> dict:
    """Obtiene detalles de un lugar en Google Places"""
    try:
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        response = await client.get(url, params={
            "place_id": place_id,
            "fields": "name,formatted_phone_number,website,opening_hours",
            "language": "es",
            "key": api_key
        })

        result = response.json().get("result", {})
        return {
            "telefono": result.get("formatted_phone_number", ""),
            "website": result.get("website", ""),
        }
    except:
        return {}

async def extract_from_website(website: str) -> dict:
    """Extrae emails, teléfonos y contactos del sitio web de la empresa"""
    extra = {"emails": [], "telefonos": [], "equipo": []}

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            headers = random.choice(HEADERS_LIST)
            response = await client.get(website, headers=headers)

            if response.status_code == 200:
                text = response.text
                soup = BeautifulSoup(text, 'html.parser')

                # Extraer emails
                email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                emails = re.findall(email_pattern, text)
                filtered_emails = [
                    e for e in emails
                    if not any(ext in e for ext in ['.png', '.jpg', '.gif', '.svg', '.css'])
                    and not any(skip in e for skip in ['example', 'test', 'noreply', 'no-reply'])
                ]
                extra["emails"] = list(set(filtered_emails))[:3]

                # Extraer teléfonos mexicanos
                phone_pattern = r'(?:\+52|52)?[\s.-]?\(?(?:\d{2,3})\)?[\s.-]?\d{3,4}[\s.-]?\d{4}'
                phones = re.findall(phone_pattern, text)
                extra["telefonos"] = list(set(phones))[:2]

                # Buscar página de equipo/nosotros
                contact_links = []
                for a in soup.find_all('a', href=True):
                    href = a.get('href', '').lower()
                    text_link = a.text.lower()
                    if any(word in href or word in text_link for word in ['equipo', 'nosotros', 'about', 'team', 'contacto']):
                        contact_links.append(href)

                if extra["emails"]:
                    extra["contacto"] = extra["emails"][0]

    except Exception as e:
        print(f"Error extrayendo website {website}: {e}")

    return extra

async def search_people(job_title: str, company: str = "", location: str = "México") -> dict:
    """Busca personas por puesto usando Google Dorks hacia LinkedIn"""
    people = []

    try:
        # Google Dork para LinkedIn
        query = f'site:linkedin.com/in "{job_title}"'
        if company:
            query += f' "{company}"'
        if location:
            query += f' "{location}"'

        url = f"https://www.google.com/search?q={query.replace(' ', '+')}&num=10&hl=es"

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            headers = random.choice(HEADERS_LIST)
            response = await client.get(url, headers=headers)
            await human_delay(1, 2)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                for result in soup.find_all('div', class_=['g', 'tF2Cxc'])[:10]:
                    title_el = result.find('h3')
                    link_el = result.find('a', href=True)
                    snippet_el = result.find(['div', 'span'], class_=['VwiC3b', 'yXK7lf'])

                    if title_el:
                        href = ""
                        if link_el:
                            href = link_el.get('href', '')
                            if '/url?q=' in href:
                                href = href.split('/url?q=')[1].split('&')[0]

                        if 'linkedin.com/in/' in href:
                            title_text = title_el.text
                            name = ""
                            puesto = job_title

                            if ' - ' in title_text:
                                parts = title_text.split(' - ')
                                name = parts[0].strip()
                                if len(parts) > 1:
                                    puesto = parts[1].replace('| LinkedIn', '').strip()
                            elif '|' in title_text:
                                parts = title_text.split('|')
                                name = parts[0].strip()

                            if name:
                                people.append({
                                    "nombre": name,
                                    "puesto": puesto,
                                    "empresa": company,
                                    "ubicacion": location,
                                    "linkedin_url": href,
                                    "descripcion": snippet_el.text[:150] if snippet_el else ""
                                })

    except Exception as e:
        print(f"Error en search_people: {e}")

    return {
        "people": people,
        "total_found": len(people),
        "search_query": f"{job_title} en {company or location}"
    }

async def get_company_details(company_name: str, website: str = "") -> dict:
    """Obtiene detalles completos de una empresa"""
    details = {
        "nombre": company_name,
        "website": website,
        "emails": [],
        "telefonos": [],
        "descripcion": "",
        "noticias": []
    }

    try:
        # Buscar sitio web si no se tiene
        if not website:
            website = await find_company_website(company_name)
            details["website"] = website

        # Extraer datos del sitio web
        if website:
            web_data = await extract_from_website(website)
            details.update(web_data)

        # Buscar noticias recientes
        noticias = await search_company_news(company_name)
        details["noticias"] = noticias

    except Exception as e:
        print(f"Error en get_company_details: {e}")

    return details

async def find_company_website(company_name: str) -> str:
    """Encuentra el sitio web oficial de una empresa"""
    try:
        query = f'"{company_name}" sitio oficial Mexico'
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}&num=5"

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            headers = random.choice(HEADERS_LIST)
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                for a in soup.find_all('a', href=True):
                    href = a.get('href', '')
                    if '/url?q=' in href:
                        href = href.split('/url?q=')[1].split('&')[0]

                    skip = ['google.com', 'linkedin.com', 'facebook.com', 'youtube.com', 'wikipedia.org']
                    if href.startswith('http') and not any(s in href for s in skip):
                        return href
    except:
        pass
    return ""

async def search_company_news(company_name: str) -> list:
    """Busca noticias recientes de una empresa"""
    noticias = []

    try:
        query = f'"{company_name}" noticias 2024 2025'
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=nws&num=5"

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            headers = random.choice(HEADERS_LIST)
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                for result in soup.find_all('div', class_=['g', 'SoaBEf', 'WlydOe'])[:3]:
                    title_el = result.find('h3')
                    if title_el:
                        noticias.append(title_el.text.strip())

    except Exception as e:
        print(f"Error buscando noticias: {e}")

    return noticias
