#!/usr/bin/env python3
"""
SUSE RMT Log Generator for PagerDuty Demo
Generates realistic logs and sends them to Loki
"""

import requests
import yaml
import time
import random
import argparse
import os
import sys
from datetime import datetime
from string import Template
from dotenv import load_dotenv

load_dotenv()

class LogGenerator:
    def __init__(self, config_path="config/services.yaml"):
        """Initialize log generator with configuration"""
        if not os.path.exists(config_path):
            print(f"❌ Error: Config file not found: {config_path}")
            sys.exit(1)

        with open(config_path, 'r') as f:
            config_content = os.path.expandvars(f.read())
            self.config = yaml.safe_load(config_content)

        self.loki_url = self.config['loki']['url'] + "/loki/api/v1/push"
        self.services = {k: v for k, v in self.config['services'].items() if v.get('enabled', True)}
        self.stats = {'total': 0, 'by_level': {}, 'by_service': {}}

        print(f"✅ Loaded {len(self.services)} services from config")

    def generate_log_message(self, service_name, service_config, force_level=None):
        """Generate a single log message"""
        patterns = service_config['log_patterns']

        if force_level:
            patterns = [p for p in patterns if p['level'] == force_level]
            if not patterns:
                raise ValueError(f"No patterns found for level: {force_level}")
            pattern = random.choice(patterns)
        else:
            # Weighted random selection
            weights = [p['weight'] for p in patterns]
            pattern = random.choices(patterns, weights=weights)[0]

        level = pattern['level']
        template_str = random.choice(pattern['templates'])

        # Replace attributes
        attributes = pattern.get('attributes', {})
        replacements = {}
        for key, values in attributes.items():
            replacements[key] = str(random.choice(values))

        template = Template(template_str)
        message = template.safe_substitute(replacements)

        instance = random.choice(service_config['instances'])

        return {
            'level': level,
            'service': service_name,
            'instance': instance,
            'message': message
        }

    def send_to_loki(self, log_entry):
        """Send log entry to Loki"""
        timestamp = str(int(time.time() * 1e9))

        payload = {
            "streams": [{
                "stream": {
                    "job": "rmt-servers",
                    "level": log_entry['level'],
                    "service": log_entry['service'],
                    "instance": log_entry['instance']
                },
                "values": [[timestamp, log_entry['message']]]
            }]
        }

        try:
            response = requests.post(self.loki_url, json=payload, timeout=5)
            response.raise_for_status()

            # Update stats
            self.stats['total'] += 1
            self.stats['by_level'][log_entry['level']] = self.stats['by_level'].get(log_entry['level'], 0) + 1
            self.stats['by_service'][log_entry['service']] = self.stats['by_service'].get(log_entry['service'], 0) + 1

            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Error sending to Loki: {e}")
            return False

    def burst_errors(self, count=6, error_type="FATAL"):
        """Generate a burst of errors to trigger alert"""
        print(f"\n🔥 Generating {count} {error_type} errors to trigger alert...")
        print(f"{'='*70}")

        for i in range(count):
            service_name = random.choice(list(self.services.keys()))
            service_config = self.services[service_name]

            log_entry = self.generate_log_message(service_name, service_config, force_level=error_type)

            if self.send_to_loki(log_entry):
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"  [{i+1}/{count}] [{timestamp}] [{log_entry['level']:5}] {log_entry['service']:20} | {log_entry['instance']:30}")
                print(f"           └─ {log_entry['message'][:80]}...")

            time.sleep(1)  # Small delay between errors

        print(f"{'='*70}")
        print(f"✅ Burst complete! Alert should trigger in ~1 minute.\n")

    def run(self, duration_minutes=None, verbose=False):
        """Run log generation"""
        print(f"\n{'='*70}")
        print(f"🚀 SUSE RMT Log Generator - PagerDuty Demo")
        print(f"{'='*70}")
        print(f"📊 Loki URL: {self.loki_url}")
        print(f"🔧 Services: {', '.join(self.services.keys())}")

        if duration_minutes:
            print(f"⏱️  Duration: {duration_minutes} minutes")
            end_time = time.time() + (duration_minutes * 60)
        else:
            print(f"⏱️  Duration: Continuous (Ctrl+C to stop)")
            end_time = None

        print(f"{'='*70}\n")

        last_stats_time = time.time()

        try:
            while True:
                if end_time and time.time() >= end_time:
                    break

                # Generate logs for each service based on rate
                for service_name, service_config in self.services.items():
                    rate = service_config.get('rate_per_minute', 10)

                    # Calculate how many logs to send this iteration (1 second)
                    logs_to_send = max(1, rate // 60)

                    for _ in range(logs_to_send):
                        log_entry = self.generate_log_message(service_name, service_config)

                        if self.send_to_loki(log_entry):
                            if verbose:
                                timestamp = datetime.now().strftime("%H:%M:%S")
                                print(f"[{timestamp}] [{log_entry['level']:5}] {log_entry['service']:20} | {log_entry['instance']:30} | {log_entry['message'][:60]}...")

                # Print stats every 60 seconds
                if time.time() - last_stats_time >= 60:
                    print(f"\n📈 Stats: Total={self.stats['total']}, Levels={self.stats['by_level']}, Services={self.stats['by_service']}\n")
                    last_stats_time = time.time()

                time.sleep(1)

        except KeyboardInterrupt:
            print("\n\n⏹️  Stopping log generation...")

        print(f"\n{'='*70}")
        print(f"📊 Final Statistics")
        print(f"{'='*70}")
        print(f"Total logs sent: {self.stats['total']}")
        print(f"\nBy level:")
        for level, count in sorted(self.stats['by_level'].items()):
            percentage = (count / self.stats['total'] * 100) if self.stats['total'] > 0 else 0
            print(f"  {level:5}: {count:5} ({percentage:5.1f}%)")
        print(f"\nBy service:")
        for service, count in sorted(self.stats['by_service'].items()):
            percentage = (count / self.stats['total'] * 100) if self.stats['total'] > 0 else 0
            print(f"  {service:20}: {count:5} ({percentage:5.1f}%)")
        print(f"{'='*70}\n")

def main():
    parser = argparse.ArgumentParser(
        description="SUSE RMT Log Generator for PagerDuty Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate logs for 30 minutes
  python log_generator.py --duration 30

  # Generate logs with verbose output
  python log_generator.py --duration 10 --verbose

  # Trigger FATAL alert (6 errors)
  python log_generator.py --burst-errors 6 --error-type FATAL

  # Trigger HTTP 500 alert
  python log_generator.py --burst-errors 6 --error-type ERROR

  # Run continuously
  python log_generator.py --verbose
        """
    )
    parser.add_argument('--config', default='config/services.yaml', help='Path to config file')
    parser.add_argument('--duration', type=int, help='Duration in minutes (omit for continuous)')
    parser.add_argument('--burst-errors', type=int, help='Generate burst of errors to trigger alert')
    parser.add_argument('--error-type', choices=['FATAL', 'ERROR'], default='FATAL', help='Type of error for burst')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output (show each log)')

    args = parser.parse_args()

    try:
        generator = LogGenerator(args.config)

        if args.burst_errors:
            generator.burst_errors(count=args.burst_errors, error_type=args.error_type)
        else:
            generator.run(duration_minutes=args.duration, verbose=args.verbose)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
