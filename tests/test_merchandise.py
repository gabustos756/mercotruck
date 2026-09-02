import pytest
from app.domain.services.merchandise_service import clean_product_name, categorizar_mercaderia, strip_accents

class TestMerchandiseCleaning:
    def test_clean_product_with_customs_tilde(self):
        assert clean_product_name("(8PK1435   ~ CORREAS DE TRANSMISION~ DAYCO~ M") == "CORREAS DE TRANSMISION"
        assert clean_product_name("000000218121 ~SOLVENTE X-DSP 60/90") == "SOLVENTE X-DSP 60/90"
        assert clean_product_name("0000374271 ~POLIETILENO~DOW~INDUSTRIAL~BOLSAS") == "POLIETILENO"
        assert clean_product_name("0000374342 ~POLIETILENO~DOW~NG6995 MEDIUM~EN") == "POLIETILENO"
        assert clean_product_name("0001 ~ ACEITE DE OLIVA") == "ACEITE DE OLIVA"
        assert clean_product_name("0001 ~ ACEITE REFINADO~ G.D.L.P.-F~ 100") == "ACEITE REFINADO"
        assert clean_product_name("0001 ~ CARBON VEGETAL~ ARGECOSOL-F~ NO") == "CARBON VEGETAL"
        assert clean_product_name("0001 ~ HARINA DE SANGRE AVIAR~ YARUBA S") == "HARINA DE SANGRE AVIAR"
        assert clean_product_name("0001 ~ HARINA DE SANGRE AVIAR~ YERUVA S") == "HARINA DE SANGRE AVIAR"
        assert clean_product_name("0001 ~ POLISULFURO DE CALCIO~ A.A.-F~ E") == "POLISULFURO DE CALCIO"
        assert clean_product_name("0001 ~OREGANO") == "OREGANO"
        assert clean_product_name("0001-1-BUC-45 ~BALDE (RECIPIENTE) DE PAPEL") == "BALDE (RECIPIENTE) DE PAPEL"
        assert clean_product_name("0001CAL ~CAL VIVA(HIDRATADA)") == "CAL VIVA (HIDRATADA)"
        assert clean_product_name("001 ~ CHAPA DE GRANITO ~ ONEMAR -F ~") == "CHAPA DE GRANITO"
        assert clean_product_name("001-SOJA ~SOJA DESACTIVADA") == "SOJA DESACTIVADA"

    def test_clean_product_without_tilde(self):
        assert clean_product_name("PANTALON DE VESTIR CABALLERO") == "PANTALON DE VESTIR CABALLERO"
        assert clean_product_name("HARINA DE PESCADO SUPREMA") == "HARINA DE PESCADO SUPREMA"
        assert clean_product_name("00123 - HARINA DE TRIGO") == "HARINA DE TRIGO"

    def test_clean_product_null_or_empty(self):
        assert clean_product_name(None) == "MERCADERIA GENERAL"
        assert clean_product_name("") == "MERCADERIA GENERAL"
        assert clean_product_name("nan") == "MERCADERIA GENERAL"
        assert clean_product_name("None") == "MERCADERIA GENERAL"


class TestMerchandiseCategorization:
    def test_pantalon_not_classified_as_pan(self):
        # Evitar el bug clásico de 'PAN' dentro de 'PANTALON'
        cat = categorizar_mercaderia("PANTALON DE VESTIR MASCULINO")
        assert cat == "Textil y calzado"

    def test_harina_de_pescado_prioritized_over_cereales(self):
        # Frase compuesta específica antes de unigrama 'HARINA'
        cat = categorizar_mercaderia("HARINA DE PESCADO SUPREMA")
        assert cat == "Alimentación animal"

    def test_harina_de_sangre_prioritized_over_cereales(self):
        cat = categorizar_mercaderia("0001 ~ HARINA DE SANGRE AVIAR~ YERUVA S")
        assert cat == "Alimentación animal"

    def test_resina_plastica_prioritized_over_resina_quimica(self):
        cat = categorizar_mercaderia("RESINA PLASTICA EN PELLETS DOW")
        assert cat == "Plásticos y polímeros"

    def test_carbonato_not_classified_as_carbon_combustible(self):
        cat = categorizar_mercaderia("CARBONATO DE CALCIO INDUSTRIAL")
        assert cat == "Minerales y fertilizantes"

    def test_carbon_vegetal_combustible(self):
        cat = categorizar_mercaderia("0001 ~ CARBON VEGETAL~ ARGECOSOL-F~ NO")
        assert cat == "Combustibles y gas"

    def test_aceite_not_intercepted_by_te(self):
        # 'TE' en 'ACEITE' no debe coincidir gracias a los límites de palabra (\b)
        cat = categorizar_mercaderia("ACEITE DE OLIVA EXTRA VIRGEN")
        assert cat == "Aceites y grasas"

    def test_te_infusiones(self):
        cat = categorizar_mercaderia("TE EN SAQUITOS LA VIRGINIA")
        assert cat == "Yerba y infusiones"

    def test_correas_de_transmision_autopartes(self):
        cat = categorizar_mercaderia("(8PK1435   ~ CORREAS DE TRANSMISION~ DAYCO~ M")
        assert cat == "Vehículos y autopartes"

    def test_cal_viva_materiales(self):
        cat = categorizar_mercaderia("0001CAL ~CAL VIVA(HIDRATADA)")
        assert cat == "Materiales construcción"

    def test_oregano_especias(self):
        cat = categorizar_mercaderia("0001 ~OREGANO")
        assert cat == "Frutas y verduras"

    def test_strip_accents(self):
        assert strip_accents("FÉCULA DE MAÍZ") == "FECULA DE MAIZ"
        assert strip_accents("ALMÍBAR Y JABÓN") == "ALMIBAR Y JABON"
