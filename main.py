from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import re
from datetime import datetime

# Cargar archivo CSV
csv_path = r"C:\Users\57318\Prueba_simit.csv"
df = pd.read_csv(csv_path, sep=";", dtype={'CODIGO CLIENTE': str}, keep_default_na=False)

# Asegurar columnas necesarias
if 'MULTAS Y COMPARENDOS' not in df.columns:
    df.rename(columns={'MULTAS': 'MULTAS Y COMPARENDOS'}, inplace=True)
for col in ['MULTAS Y COMPARENDOS', 'SECRETARIA', 'FECHA DE RESOLUCION', 'PLACA']:
    if col not in df.columns:
        df[col] = ''
    df[col] = df[col].astype(str)

# Configurar navegador
options = Options()
options.add_experimental_option("detach", True)
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)
driver.get("https://www.fcm.org.co/simit/#/home-public")
driver.maximize_window()

# Cerrar modal bloqueante si existe
try:
    wait.until(EC.invisibility_of_element_located((By.ID, "whcModal")))
except:
    pass

# Cerrar modal informativo
try:
    modal_close = wait.until(EC.presence_of_element_located(
        (By.XPATH, '//*[@id="modalInformation"]/div/div/div[1]/button/span')))
    driver.execute_script("arguments[0].click();", modal_close)
except Exception as e:
    print(f"[!] No se pudo cerrar el modal inicial: {e}")

# Iterar sobre las cédulas directamente en df
for index, row in df.iterrows():
    if str(row['MULTAS Y COMPARENDOS']).strip() not in ['', 'nan', 'None']:
        continue

    cedula = str(row['CODIGO CLIENTE']).split('.')[0]

    try:
        input_xpath = '//*[@id="txtBusqueda"]'
        input_field = wait.until(EC.element_to_be_clickable((By.XPATH, input_xpath)))
        input_field.clear()
        input_field.send_keys(cedula)
        input_field.send_keys(Keys.ENTER)

        # Pop-up de selección de tipo de documento
        try:
            popup_wait = WebDriverWait(driver, 3)
            cedula_radio = popup_wait.until(EC.presence_of_element_located((By.ID, 'rdPerRep1')))
            driver.execute_script("arguments[0].click();", cedula_radio)

            continuar_btn = popup_wait.until(EC.element_to_be_clickable((
                By.XPATH, '//button[contains(text(),"Continuar") and contains(@class, "btn-block")]')))
            driver.execute_script("arguments[0].click();", continuar_btn)
            print(f"[✓] Pop-up: Seleccionado tipo 'Cédula' y continuado.")

            # Segundo pop-up "continuar"
            try:
                segundo_popup = WebDriverWait(driver, 3).until(
                    EC.visibility_of_element_located((By.XPATH, '//div[contains(text(), "varios resultados para la búsqueda")]'))
                )
                continuar_btn2 = wait.until(EC.element_to_be_clickable((
                    By.XPATH, '//div[contains(@class, "modal-content")]//button[contains(text(), "Continuar")]')))
                driver.execute_script("arguments[0].click();", continuar_btn2)
                print(f"[ℹ️] Segundo pop-up: Seleccionado continuar con múltiples resultados.")
            except:
                pass

        except Exception as e:
            print(f"[ℹ️] No apareció o falló el pop-up: {e}")

        # Obtener número de multas y comparendos
        multas_xpath = '//label[contains(text(), "Multas:")]/following-sibling::span/strong'
        comparendos_xpath = '//label[contains(text(), "Comparendos:")]/following-sibling::span/strong'

        multas_element = wait.until(EC.presence_of_element_located((By.XPATH, multas_xpath)))
        comparendos_element = wait.until(EC.presence_of_element_located((By.XPATH, comparendos_xpath)))

        num_multas = int(multas_element.text.strip())
        num_comparendos = int(comparendos_element.text.strip())
        total = num_multas + num_comparendos

        df.at[index, 'MULTAS Y COMPARENDOS'] = str(total)

        if total == 0:
            df.at[index, 'FECHA DE RESOLUCION'] = "no tiene multas ni comparendos"
            df.at[index, 'SECRETARIA'] = "no tiene multas ni comparendos"
            df.at[index, 'PLACA'] = "no tiene multas ni comparendos"
            print(f"[✓] {cedula}: 0 multas ni comparendos")
            df.to_csv(csv_path, sep=';', index=False, na_rep='')
            continue

        # Buscar tabla de detalles
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="multaTable"]')))
            rows = driver.find_elements(By.XPATH, '//*[@id="multaTable"]/tbody/tr')

            fechas_info = []
            for row_elem in rows:
                try:
                    tipo_td = row_elem.find_element(By.XPATH, './td[@data-label="Tipo"]')
                    tipo_text = tipo_td.text
                    match = re.search(r'Fecha (resolución|coactivo):\s*(\d{2}/\d{2}/\d{4})', tipo_text, re.IGNORECASE)
                    if match:
                        fecha_str = match.group(2)
                        fecha_dt = datetime.strptime(fecha_str, "%d/%m/%Y")
                        fechas_info.append((fecha_dt, row_elem))
                except:
                    continue

            if fechas_info:
                fecha_mas_reciente, fila = max(fechas_info, key=lambda x: x[0])
                secretaria = fila.find_element(By.XPATH, './td[@data-label="Secretaría"]').text.strip()
                placa = fila.find_element(By.XPATH, './td[@data-label="Placa"]').text.strip()

                df.at[index, 'FECHA DE RESOLUCION'] = fecha_mas_reciente.strftime("%d/%m/%Y")
                df.at[index, 'SECRETARIA'] = secretaria
                df.at[index, 'PLACA'] = placa
            else:
                df.at[index, 'FECHA DE RESOLUCION'] = "no tiene multas ni comparendos"
                df.at[index, 'SECRETARIA'] = "no tiene multas ni comparendos"
                df.at[index, 'PLACA'] = "no tiene multas ni comparendos"

        except:
            df.at[index, 'FECHA DE RESOLUCION'] = "no tiene multas ni comparendos"
            df.at[index, 'SECRETARIA'] = "no tiene multas ni comparendos"
            df.at[index, 'PLACA'] = "no tiene multas ni comparendos"

        print(f"[✓] {cedula}: {total} en total")

    except Exception as e:
        print(f"[✗] Error con la cédula {cedula}: {e}")
        df.at[index, 'MULTAS Y COMPARENDOS'] = ''
        df.at[index, 'FECHA DE RESOLUCION'] = ''
        df.at[index, 'SECRETARIA'] = ''
        df.at[index, 'PLACA'] = ''

    # 🔒 Guardar después de cada iteración
    df.to_csv(csv_path, sep=';', index=False, na_rep='')

# Finalizar
driver.quit()
