"""
Live integration test — run from a shell that has WU_API_KEY set.
Usage: .venv/bin/python test_live.py
"""
import asyncio
import wunderground_server


async def run() -> None:
    print("=" * 60)
    print("TEST 1: Station (no city/state) — get_station_conditions")
    print("=" * 60)
    result = await wunderground_server.get_station_conditions()
    print(result)

    print()
    print("=" * 60)
    print("TEST 2: City/state — get_current_conditions_for_city_state")
    print("         city='Kyle', state='TX'")
    print("=" * 60)
    result = await wunderground_server.get_current_conditions_for_city_state(
        "Kyle", "TX"
    )
    print(result)

    print()
    print("=" * 60)
    print("TEST 2b: City/state — get_current_conditions_for_city_state")
    print("          city='Kyle, TX' (combined)")
    print("=" * 60)
    result = await wunderground_server.get_current_conditions_for_city_state(
        "Kyle, TX"
    )
    print(result)

    print()
    print("=" * 60)
    print("TEST 3: City/state forecast — get_forecast_for_city_state")
    print("         city='Kyle', state='TX'")
    print("=" * 60)
    result = await wunderground_server.get_forecast_for_city_state(
        "Kyle", "TX"
    )
    print(result)

    print()
    print("=" * 60)
    print("TEST 4: Station forecast — get_station_forecast")
    print("=" * 60)
    result = await wunderground_server.get_station_forecast()
    print(result)


asyncio.run(run())
