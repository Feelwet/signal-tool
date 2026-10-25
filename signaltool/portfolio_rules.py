"""«Signal-boka» – fryste papirhandelsregler (AnalBots rules_v1). Endres aldri på stedet: nye regler = ny versjon."""
RULES_VERSION = "rules_v1"

RULES = {
    "version": RULES_VERSION,
    "start_nok": 1_000_000.0,
    "buy_category": "kjop",            # bare Kjøp
    "fill": "sluttkurs dagen etter signalet",
    "position_pct": 0.05,              # 5 % av kontoverdi ved kjøp
    "max_positions": 20,
    "add_to_position": False,
    "cash_rate": 0.0,
    "hold_trading_days": 60,
    "sell_on_red_flag": True,
    "sell_on_folg_or_lower": True,     # Følg eller ute av lista; Hold selges IKKE
    "price_target": None,
    "stop_loss": None,
    "cost_each_way": 0.002,
    "cost_each_way_illiquid": 0.005,
    "fx": "USD → NOK samme dags kurs; valutaeffekt logges separat",
    "benchmark": "OSEBX/S&P 500 vektet etter porteføljens faktiske beholdning",
    "min_closed_for_returns": 30,
    "order_expiry_runs": 5,            # ordre uten kurs i 5 kjøringer kanselleres
}
