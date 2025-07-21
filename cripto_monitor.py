import requests
import time
import json
import os
from datetime import datetime, timedelta, timezone

# --- Constantes de Configuración ---
STABLECOIN_BLACKLIST = {
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
    "USTCdDR9iHykMv51f6Vp3a1yGfg3ASkfvA1Rk1gpepU",   # UST (Terra)
    "9vMJfxuKxXBoEa7rM12mYLMwP5yChFj2jXo3iDR3U5S2",  # USH
    "A9mUU4qviSctJVPJdBJWkb28deg915LYJKrzQ19ji3FM",  # PAI
    "Ea5SjE2Y6yvCeW5dYTn7PY2MCXVEkLdM9r1As5MVvaJL",  # mSOL
    "USDH1SM1ojwWUga67PGrgA8eB2T12AgfCE15KVIor1s",   # USDH
    "UxdJBfiHbdw2iMRJ1hA2oHk2Jd2172G1c32i8n22Y4Y",   # UXD
}
SOL_TOKEN_ADDRESS = "So11111111111111111111111111111111111111112"
POPULAR_TOKEN_ADDRESSES = [
    "EKpQGSFDjgmoocSBMDwPkabapDMHbQc8KzNFoYLtUqRM", # WIF
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", # BONK
    "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", # POPCAT
    "ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82", # BOME
]
CHAIN_ID = "solana"
MIN_LIQUIDITY_USD = 1000000
MIN_VOLUME_H24_USD = 1000000
MIN_AGE_HOURS = 122
N_TOP_PAIRS = 5
MONITOR_INTERVAL_SECONDS = 5

def clear_screen():
    """Limpia la pantalla de la consola."""
    os.system('cls' if os.name == 'nt' else 'clear')

def buscar_pares_iniciales():
    """Busca y filtra los 5 pares principales para monitorear."""
    all_pares = []
    for token_address in POPULAR_TOKEN_ADDRESSES:
        url = f"https://api.dexscreener.com/latest/dex/search?q={token_address}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            pares = data.get("pairs", [])
            all_pares.extend(pares)
        except requests.exceptions.RequestException as e:
            print(f"Error al conectar con la API para {token_address}: {e}")
            continue

    # --- Filtrado ---
    pares_filtrados = []
    ahora = datetime.now(timezone.utc)
    limite_antiguedad = ahora - timedelta(hours=MIN_AGE_HOURS)

    for par in all_pares:
        if par.get("chainId") != CHAIN_ID:
            continue

        # Determinar la dirección del otro token
        base_token_address = par.get("baseToken", {}).get("address")
        quote_token_address = par.get("quoteToken", {}).get("address")
        other_token_address = ""
        if base_token_address == SOL_TOKEN_ADDRESS:
            other_token_address = quote_token_address
        else:
            other_token_address = base_token_address

        # Descartar si el otro token es un stablecoin
        if other_token_address in STABLECOIN_BLACKLIST:
            continue
            
        if par.get("liquidity", {}).get("usd", 0) < MIN_LIQUIDITY_USD:
            continue
        if par.get("volume", {}).get("h24", 0) < MIN_VOLUME_H24_USD:
            continue
        
        timestamp_creacion_ms = par.get("pairCreatedAt", 0)
        if timestamp_creacion_ms:
            fecha_creacion = datetime.fromtimestamp(timestamp_creacion_ms / 1000, timezone.utc)
            if fecha_creacion > limite_antiguedad:
                continue
        else:
            continue
        
        pares_filtrados.append(par)

    pares_ordenados = sorted(pares_filtrados, key=lambda p: p.get("volume", {}).get("h24", 0), reverse=True)
    return pares_ordenados[:N_TOP_PAIRS]

def simular_compra(pares):
    """Simula la compra de 1 SOL para cada par."""
    inversiones = []
    print("\n--- Simulación de Compra ---")
    for par in pares:
        precio_nativo = float(par.get("priceNative", 0))
        if precio_nativo == 0:
            print(f"Advertencia: Precio nativo 0 para {par.get('baseToken', {}).get('symbol')}/{par.get('quoteToken', {}).get('symbol')}. Saltando.")
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

        print(f"Par: {par.get('baseToken', {}).get('symbol')}/{par.get('quoteToken', {}).get('symbol')} | Precio Nativo: {precio_nativo:.6f} | Cantidad Comprada ({token_objetivo_simbolo}): {cantidad_token_comprado:.6f}")
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
                    print(f"Advertencia: No se encontró el par actualizado para {inversion['tokenSymbol']}. Saltando.")
                    continue

                precio_actual = float(par_actual.get("priceNative", 0))
                if precio_actual == 0:
                    print(f"Advertencia: Precio actual 0 para {inversion['tokenSymbol']}. Saltando.")
                    continue

                valor_actual_sol = 0
                if par_actual["baseToken"]["address"] == SOL_TOKEN_ADDRESS:
                    valor_actual_sol = inversion["cantidadComprada"] / precio_actual
                else:
                    valor_actual_sol = inversion["cantidadComprada"] * precio_actual

                resultado = "GANANCIA" if valor_actual_sol > 1 else "PÉRDIDA"
                if abs(valor_actual_sol - 1) < 0.0001: resultado = "NEUTRO"
                
                print(f"{inversion['tokenSymbol']:<15} {valor_actual_sol:<25.6f} {resultado:<15} | Precio Actual: {precio_actual:.6f}")

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
