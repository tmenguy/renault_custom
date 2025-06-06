"""CLI function for a vehicle."""

from typing import Any
from typing import Optional

import aiohttp
import click
from tabulate import tabulate

from ..cli import helpers
from ..cli import renault_vehicle
from ..kamereon.models import KamereonVehicleDetails


@click.command()
@helpers.start_end_option(False)
@click.pass_obj
@helpers.coro_with_websession
async def sessions(
    ctx_data: dict[str, Any],
    *,
    start: str,
    end: str,
    websession: aiohttp.ClientSession,
) -> None:
    """Display charge sessions."""
    parsed_start, parsed_end = helpers.parse_dates(start, end)

    vehicle = await renault_vehicle.get_vehicle(
        websession=websession, ctx_data=ctx_data
    )
    details = await vehicle.get_details()
    response = await vehicle.get_charges(start=parsed_start, end=parsed_end)
    charges: list[dict[str, Any]] = response.raw_data["charges"]
    if not charges:
        click.echo("No data available.")
        return

    headers = [
        "Charge start",
        "Charge end",
        "Duration",
        "Power (kW)",
        "Started at",
        "Finished at",
        "Charge gained",
        "Energy gained",
        "Power level",
        "Status",
    ]
    click.echo(
        tabulate(
            [_format_charges_item(item, details) for item in charges], headers=headers
        )
    )


def _format_charges_item(
    item: dict[str, Any], details: KamereonVehicleDetails
) -> list[str]:
    duration_unit = (
        "minutes"
        if details.reports_charge_session_durations_in_minutes()
        else "seconds"
    )
    return [
        helpers.get_display_value(item.get("chargeStartDate"), "tzdatetime"),
        helpers.get_display_value(item.get("chargeEndDate"), "tzdatetime"),
        helpers.get_display_value(item.get("chargeDuration"), duration_unit),
        helpers.get_display_value(item.get("chargeStartInstantaneousPower"), "kW"),
        helpers.get_display_value(item.get("chargeStartBatteryLevel"), "%"),
        helpers.get_display_value(item.get("chargeEndBatteryLevel"), "%"),
        helpers.get_display_value(item.get("chargeBatteryLevelRecovered"), "%"),
        helpers.get_display_value(item.get("chargeEnergyRecovered"), "kWh"),
        helpers.get_display_value(item.get("chargePower")),
        helpers.get_display_value(item.get("chargeEndStatus")),
    ]


@click.command()
@helpers.start_end_option(True)
@click.pass_obj
@helpers.coro_with_websession
async def history(
    ctx_data: dict[str, Any],
    *,
    start: str,
    end: str,
    period: Optional[str],
    websession: aiohttp.ClientSession,
) -> None:
    """Display charge history."""
    parsed_start, parsed_end = helpers.parse_dates(start, end)
    period = period or "month"

    vehicle = await renault_vehicle.get_vehicle(
        websession=websession, ctx_data=ctx_data
    )
    response = await vehicle.get_charge_history(
        start=parsed_start, end=parsed_end, period=period
    )
    charge_summaries: list[dict[str, Any]] = response.raw_data["chargeSummaries"]
    if not charge_summaries:
        click.echo("No data available.")
        return

    headers = [
        period.capitalize(),
        "Number of charges",
        "Total time charging",
        "Errors",
    ]
    click.echo(
        tabulate(
            [_format_charge_history_item(item, period) for item in charge_summaries],
            headers=headers,
        )
    )


def _format_charge_history_item(item: dict[str, Any], period: str) -> list[str]:
    return [
        helpers.get_display_value(item.get(period)),
        helpers.get_display_value(item.get("totalChargesNumber")),
        helpers.get_display_value(item.get("totalChargesDuration"), "minutes"),
        helpers.get_display_value(item.get("totalChargesErrors")),
    ]
