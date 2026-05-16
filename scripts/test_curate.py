#!/usr/bin/env python3
"""Focused regression checks for news category drift."""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("curate", ROOT / "scripts" / "curate.py")
curate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(curate)


CASES = [
    (
        "Citi AAdvantage Globe Card American Admirals Club Passes Explained",
        "The Citi / AAdvantage Globe Mastercard is American Airlines' new premium credit card.",
        "Tips",
    ),
    (
        "Hyatt Wins Loyalty Program Tax Fight That Could Save $589 Million — While Members Pay More Points For Free Nights",
        "Hyatt won an appeals court fight over how its loyalty program is taxed.",
        None,
    ),
    (
        "Chase Sapphire Reserve® Protections That Can Save You Money When Things Go Wrong",
        "The Chase Sapphire Reserve provides comprehensive benefits simply for being a cardmember.",
        "Tips",
    ),
    (
        "American Airlines Launches New Shopping Portal Bonus Worth up to 2,000 Miles",
        "American Airlines has launched a new airline shopping portal promotion.",
        "Deals",
    ),
    (
        "Chase Launches Rare Transfer Bonus to Southwest Rapid Rewards — But Only for a Few Weeks",
        "Chase Ultimate Rewards launched a 30% transfer bonus to Southwest Rapid Rewards.",
        "Deals",
    ),
    (
        "Mastercard launches “Taste by Priceless” Lounges",
        "Mastercard is launching new airport lounges for eligible cardholders.",
        "News",
    ),
    (
        "Intuit Launches Business Credit Card – $300 Bonus, 2% Back & No Annual Fee",
        "Intuit has launched a new business credit card.",
        "Card Updates",
    ),
    (
        "New Delta One Suites Will Include Special “Business Class Plus” Product",
        "Delta is introducing a new business class plus product.",
        None,
    ),
    (
        "LAX’s New Metro Station Set To Be Renamed For Cathay Pacific In Nearly $10 Million Deal",
        "LAX’s new Metro station is about to get an airline name.",
        None,
    ),
    (
        "Rippling Corporate Card review: A powerful all-in-one card for cash back and expense control",
        "The Rippling Corporate Card offers up to 1.75% in cash-back rewards and integrated spend management features.",
        "Tips",
    ),
    (
        "Citi AAdvantage Globe Card Flight Streak Loyalty Points Bonus Explained",
        "The Citi / AAdvantage Globe Mastercard has a flight streak loyalty points bonus.",
        "Tips",
    ),
    (
        "JetBlue and United expand Blue Sky partnership with new reciprocal elite perks",
        "JetBlue and United's Blue Sky partnership is expanding into a new phase focused on elite traveler benefits.",
        "News",
    ),
    (
        "Hurry to Score Infield Major League Baseball Tickets for Just 5,000 Capital One Miles",
        "Capital One offers a limited number of infield MLB tickets for just 5,000 miles each.",
        "Deals",
    ),
    (
        "Deal alert: Points and miles travel deals for May 2026",
        "Save, maximize and earn points and miles on various travel purchases this May.",
        "Deals",
    ),
    (
        "Great news: New price matching feature now available in some Chase Travel accounts",
        "Chase Travel accounts now have a price matching feature.",
        "News",
    ),
]


def main():
    failures = []
    for title, summary, expected in CASES:
        actual = curate.categorize(title, summary)
        if actual != expected:
            failures.append((title, expected, actual))

    if failures:
        for title, expected, actual in failures:
            print(f"FAIL: {title}\n  expected={expected!r} actual={actual!r}")
        raise SystemExit(1)

    print(f"Passed {len(CASES)} category regression checks.")


if __name__ == "__main__":
    main()
