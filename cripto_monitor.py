import requests
import time
import json
import os
from datetime import datetime, timedelta, timezone

# --- Constantes de Configuración ---
SOL_TOKEN_ADDRESS = "So11111111111111111111111111111111111111112"
CHAIN_ID = "solana"
MIN_LIQUIDITY_USD = 10000
MIN_VOLUME_H24_USD = 10000
MIN_AGE_HOURS = 12
N_TOP_PAIRS = 5
MONITOR_INTERVAL_SECONDS = 5

def clear_screen():
    """Limpia la pantalla de la consola."""
    os.system('cls' if os.name == 'nt' else 'clear')

def buscar_pares_iniciales():
    """Busca y filtra los 5 pares principales para monitorear."""
    print("Iniciando la búsqueda de pares...")
    url = f"https://api.dexscreener.com/latest/dex/search?q={SOL_TOKEN_ADDRESS}"
    try:
        print(f"Consultando API: {url}")
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        pares = data.get("pairs", [])
        print(f"API encontró {len(pares)} pares en total.")
    except requests.exceptions.RequestException as e:
        print(f"Error al conectar con la API: {e}")
        return []

    # --- Filtrado ---
    print("\nIniciando filtrado de pares...")
    pares_filtrados = []
    ahora = datetime.now(timezone.utc)
    limite_antiguedad = ahora - timedelta(hours=MIN_AGE_HOURS)
    print(f"Criterios: Liquidez > ${MIN_LIQUIDITY_USD}, Volumen (24h) > ${MIN_VOLUME_H24_USD}, Antigüedad > {MIN_AGE_HOURS} horas")


    for i, par in enumerate(pares):
        print(f"\n--- Analizando Par #{i+1}: {par.get('baseToken', {}).get('symbol')}/{par.get('quoteToken', {}).get('symbol')} ({par.get('pairAddress')[:10]}...) ---")

        if par.get("chainId") != CHAIN_ID:
            print(f"Descartado: chainId incorrecto ('{par.get('chainId')}')")
            continue

        liquidity_usd = par.get("liquidity", {}).get("usd", 0)
        if liquidity_usd < MIN_LIQUIDITY_USD:
            print(f"Descartado: Liquidez insuficiente (${liquidity_usd:.2f})")
            continue

        volume_h24 = par.get("volume", {}).get("h24", 0)
        if volume_h24 < MIN_VOLUME_H24_USD:
            print(f"Descartado: Volumen 24h insuficiente (${volume_h24:.2f})")
            continue
        
        timestamp_creacion_ms = par.get("pairCreatedAt", 0)
        if timestamp_creacion_ms:
            fecha_creacion = datetime.fromtimestamp(timestamp_creacion_ms / 1000, timezone.utc)
            if fecha_creacion > limite_antiguedad:
                print(f"Descartado: Demasiado nuevo (Creado: {fecha_creacion.strftime('%Y-%m-%d')})")
                continue
        else:
            print("Descartado: No tiene fecha de creación.")
            continue
        
        print("¡Par APROBADO!")
        pares_filtrados.append(par)

    print(f"\nFiltrado completo. Se encontraron {len(pares_filtrados)} pares que cumplen los criterios.")
    pares_ordenados = sorted(pares_filtrados, key=lambda p: p.get("volume", {}).get("h24", 0), reverse=True)
    print(f"Se seleccionarán los mejores {N_TOP_PAIRS} pares.")
    return pares_ordenados[:N_TOP_PAIRS]

def simular_compra(pares):
    """Simula la compra de 1 SOL para cada par."""
    inversiones = []
    for par in pares:
        precio_nativo = float(par.get("priceNative", 0))
        if precio_nativo == 0:
            continue

        token_objetivo_simbolo = ""
        cantidad_token_comprado = 0

        # Determinar si SOL es el token base o el de cotización
        if par["baseToken"]["address"] == SOL_TOKEN_ADDRESS:
            # El par es SOL/TOKEN. priceNative es la cantidad de TOKEN por 1 SOL.
            token_objetivo_simbolo = par["quoteToken"]["symbol"]
            cantidad_token_comprado = precio_nativo
        else:
            # El par es TOKEN/SOL. priceNative es la cantidad de SOL por 1 TOKEN.
            token_objetivo_simbolo = par["baseToken"]["symbol"]
            cantidad_token_comprado = 1 / precio_nativo

        inversiones.append({
            "pairAddress": par["pairAddress"],
            "tokenSymbol": token_objetivo_simbolo,
            "cantidadComprada": cantidad_token_comprado
        })
    return inversiones

def monitorear_precios(inversiones):
    """Inicia el bucle de monitoreo de precios."""
    if not inversiones:
        print("No hay inversiones para monitorear.")
        return

    pair_addresses = [inv["pairAddress"] for inv in inversiones]
    url = f"https://api.dexscreener.com/latest/dex/pairs/{CHAIN_ID}/{','.join(pair_addresses)}"

    while True:
        try:
            response = requests.get(url)
            if response.status_code != 200:
                time.sleep(MONITOR_INTERVAL_SECONDS)
                continue
            
            data = response.json()
            pares_actualizados = data.get("pairs", [])
            
            clear_screen()
            print(f"--- Monitoreo de Inversión (Simulada) | Actualizado: {datetime.now().strftime('%H:%M:%S')} ---")
            print("Inversión inicial: 1 SOL por cada token.\n")
            print(f"{"Token":<15} {"Valor Actual (SOL)":<25} {"Resultado":<15}")
            print("-"*60)

            for inversion in inversiones:
                par_actual = next((p for p in pares_actualizados if p["pairAddress"] == inversion["pairAddress"]), None)
                if not par_actual:
                    continue

                precio_actual = float(par_actual.get("priceNative", 0))
                if precio_actual == 0:
                    continue

                valor_actual_sol = 0
                if par_actual["baseToken"]["address"] == SOL_TOKEN_ADDRESS:
                    valor_actual_sol = inversion["cantidadComprada"] / precio_actual
                else:
                    valor_actual_sol = inversion["cantidadComprada"] * precio_actual

                resultado = "GANANCIA" if valor_actual_sol > 1 else "PÉRDIDA"
                if abs(valor_actual_sol - 1) < 0.0001: resultado = "NEUTRO"
                
                print(f"{inversion['tokenSymbol']:<15} {valor_actual_sol:<25.6f} {resultado:<15}")

            print("\n(Presiona Ctrl+C para detener)")
            time.sleep(MONITOR_INTERVAL_SECONDS)

        except requests.exceptions.RequestException:
            print("Error de conexión. Reintentando...")
            time.sleep(MONITOR_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nMonitoreo detenido.")
            break

if __name__ == "__main__":
    print("Buscando y filtrando los 5 pares de SOL más relevantes...")
    pares_seleccionados = buscar_pares_iniciales()

    if pares_seleccionados:
        print(f"Se encontraron {len(pares_seleccionados)} pares. Iniciando simulación...")
        inversiones_simuladas = simular_compra(pares_seleccionados)
        monitorear_precios(inversiones_simuladas)
    else:
        print("No se encontraron pares que cumplan los criterios para iniciar el monitoreo.")
