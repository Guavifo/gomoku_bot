#!/usr/bin/env python3
"""
Game Statistics Analyzer for Gomoku Bot Platform

Analyzes game files in the games/ directory and generates summary statistics.
Run this script periodically (e.g., after every few hundred games) to track metrics.
"""

import os
import sys
from collections import defaultdict
from typing import Any, Dict, Optional
import statistics


def parse_game_file(filepath: str) -> Optional[Dict[str, Any]]:
    """Parse a game file and extract relevant information."""
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()

        game_data = {
            'winner': None,
            'winner_color': None,
            'outcome': None,
            'total_moves': 0,
            'opening_moves': 0,
            'player_moves': 0
        }

        in_opening = False
        in_moves = False

        for line in lines:
            line = line.strip()

            # Parse winner
            if line.startswith('Winner:'):
                winner_text = line.split(':', 1)[1].strip()
                if winner_text == 'Draw':
                    game_data['winner'] = 'Draw'
                    game_data['winner_color'] = None
                else:
                    # Extract winner and color from "Username (Color)"
                    if '(' in winner_text:
                        parts = winner_text.split('(')
                        game_data['winner'] = parts[0].strip()
                        color = parts[1].rstrip(')').strip()
                        game_data['winner_color'] = color  # "Black" or "White"

            # Parse outcome
            elif line.startswith('Outcome:'):
                game_data['outcome'] = line.split(':', 1)[1].strip()

            # Track sections
            elif line == "Random Opening:":
                in_opening = True
                in_moves = False
                continue
            elif line == "Moves:":
                in_opening = False
                in_moves = True
                continue

            # Count moves
            if (in_opening or in_moves) and line.startswith('('):
                game_data['total_moves'] += 1
                if in_opening:
                    game_data['opening_moves'] += 1
                else:
                    game_data['player_moves'] += 1

        return game_data

    except Exception as e:
        print(f"Error parsing {filepath}: {e}", file=sys.stderr)
        return None


def analyze_games(games_dir: str = "games") -> None:
    """Analyze all games in the specified directory and print statistics."""

    if not os.path.exists(games_dir):
        print(f"Error: Games directory '{games_dir}' not found.")
        print("No games have been played yet.")
        return

    # Get all game files
    game_files = [f for f in os.listdir(games_dir) if f.startswith('game_') and f.endswith('.txt')]

    if not game_files:
        print(f"No game files found in '{games_dir}' directory.")
        return

    # Initialize counters
    total_games = 0
    black_wins = 0
    white_wins = 0
    draws = 0

    outcome_counts = defaultdict(int)
    move_counts = defaultdict(int)
    all_move_lengths = []

    # Parse all games
    for filename in game_files:
        filepath = os.path.join(games_dir, filename)
        game_data = parse_game_file(filepath)

        if game_data is None:
            continue

        total_games += 1

        # Count wins by result
        if game_data['winner'] == 'Draw':
            draws += 1
        elif game_data['winner_color'] == 'Black':
            black_wins += 1
        elif game_data['winner_color'] == 'White':
            white_wins += 1

        # Count outcomes
        if game_data['outcome']:
            outcome_counts[game_data['outcome']] += 1

        # Count game lengths
        total_moves = game_data['total_moves']
        move_counts[total_moves] += 1
        all_move_lengths.append(total_moves)

    # Print results
    print("=" * 70)
    print("GOMOKU GAME STATISTICS")
    print("=" * 70)
    print(f"\nTotal games analyzed: {total_games}")

    if total_games == 0:
        return

    # Win percentages
    print("\n" + "-" * 70)
    print("WIN PERCENTAGES")
    print("-" * 70)
    black_pct = (black_wins / total_games) * 100
    white_pct = (white_wins / total_games) * 100
    draw_pct = (draws / total_games) * 100

    print(f"Black wins:  {black_wins:5d} ({black_pct:5.2f}%)")
    print(f"White wins:  {white_wins:5d} ({white_pct:5.2f}%)")
    print(f"Draws:       {draws:5d} ({draw_pct:5.2f}%)")

    # Color advantage
    if black_wins + white_wins > 0:
        black_win_rate = (black_wins / (black_wins + white_wins)) * 100
        white_win_rate = (white_wins / (black_wins + white_wins)) * 100
        print(f"\nExcluding draws:")
        print(f"  Black win rate: {black_win_rate:.2f}%")
        print(f"  White win rate: {white_win_rate:.2f}%")

    # Outcome distribution
    print("\n" + "-" * 70)
    print("OUTCOME DISTRIBUTION")
    print("-" * 70)
    for outcome, count in sorted(outcome_counts.items()):
        pct = (count / total_games) * 100
        print(f"{outcome:20s}: {count:5d} ({pct:5.2f}%)")

    # Game length statistics
    print("\n" + "-" * 70)
    print("GAME LENGTH STATISTICS")
    print("-" * 70)
    if all_move_lengths:
        avg_length = statistics.mean(all_move_lengths)
        median_length = statistics.median(all_move_lengths)
        min_length = min(all_move_lengths)
        max_length = max(all_move_lengths)

        print(f"Average game length: {avg_length:.2f} moves")
        print(f"Median game length:  {median_length:.1f} moves")
        print(f"Shortest game:       {min_length} moves")
        print(f"Longest game:        {max_length} moves")

    # Game length distribution
    print("\n" + "-" * 70)
    print("GAME LENGTH DISTRIBUTION")
    print("-" * 70)
    print("Moves | Count | Percentage | Bar")
    print("-" * 70)

    # Sort by number of moves
    for moves in sorted(move_counts.keys()):
        count = move_counts[moves]
        pct = (count / total_games) * 100
        # Create a simple bar chart (1 character per 2%)
        bar_length = int(pct / 2)
        bar = '█' * bar_length
        print(f"{moves:5d} | {count:5d} | {pct:6.2f}%    | {bar}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    # Allow custom games directory as command line argument
    games_dir = sys.argv[1] if len(sys.argv) > 1 else "games"
    analyze_games(games_dir)
