#!/usr/bin/env python3
"""
SSH Configuration Verification Script

This script verifies that SSH configuration is properly set up for Ansible access:
1. Checks that the public key from bastion host is in authorized_keys on all target nodes
2. Checks that all target node host keys are in known_hosts on bastion host

Usage:
    python3 check_ssh_config.py --user <ssh_user> --key <path_to_private_key> [--inventory <inventory_file>]

Example:
    python3 check_ssh_config.py --user ubuntu --key ~/.ssh/gcp_rke2_key
"""

import argparse
import os
import sys
import subprocess
import yaml
from pathlib import Path


def load_inventory(inventory_path):
    """Load and parse Ansible inventory YAML file."""
    try:
        with open(inventory_path, 'r') as f:
            inventory = yaml.safe_load(f)
        return inventory
    except Exception as e:
        print(f"ERROR: Failed to load inventory file {inventory_path}: {e}", file=sys.stderr)
        sys.exit(1)


def get_target_hosts(inventory):
    """Extract all master and worker node IPs from inventory."""
    hosts = []
    
    # Get masters
    if 'masters' in inventory.get('all', {}).get('children', {}):
        for host_name, host_vars in inventory['all']['children']['masters'].get('hosts', {}).items():
            if 'ansible_host' in host_vars:
                hosts.append({
                    'name': host_name,
                    'ip': host_vars['ansible_host'],
                    'type': 'master'
                })
    
    # Get workers
    if 'workers' in inventory.get('all', {}).get('children', {}):
        for host_name, host_vars in inventory['all']['children']['workers'].get('hosts', {}).items():
            if 'ansible_host' in host_vars:
                hosts.append({
                    'name': host_name,
                    'ip': host_vars['ansible_host'],
                    'type': 'worker'
                })
    
    return hosts


def get_bastion_host(inventory):
    """Extract bastion host IP from inventory."""
    if 'bastion' in inventory.get('all', {}).get('children', {}):
        bastion_hosts = inventory['all']['children']['bastion'].get('hosts', {})
        for host_name, host_vars in bastion_hosts.items():
            if 'ansible_host' in host_vars:
                return host_vars['ansible_host']
            elif 'internal_ip' in host_vars:
                return host_vars['internal_ip']
    return None


def get_public_key_from_private(private_key_path):
    """Extract public key from private key file."""
    public_key_path = private_key_path + '.pub'
    
    if not os.path.exists(public_key_path):
        print(f"ERROR: Public key file not found: {public_key_path}", file=sys.stderr)
        print("      Generate it with: ssh-keygen -y -f <private_key> > <private_key>.pub", file=sys.stderr)
        return None
    
    try:
        with open(public_key_path, 'r') as f:
            public_key = f.read().strip()
        return public_key
    except Exception as e:
        print(f"ERROR: Failed to read public key file {public_key_path}: {e}", file=sys.stderr)
        return None


def check_public_key_in_authorized_keys(host_ip, user, public_key, private_key_path):
    """Check if public key exists in authorized_keys on remote host."""
    try:
        # Use ssh to check authorized_keys remotely
        # Note: This requires SSH access to work, which means the key should already be set up
        cmd = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'ConnectTimeout=5',
            '-o', 'BatchMode=yes',  # Non-interactive, fail if key auth doesn't work
            '-i', os.path.expanduser(private_key_path),
            f'{user}@{host_ip}',
            f'grep -Fx "{public_key}" ~/.ssh/authorized_keys > /dev/null 2>&1 && echo "FOUND" || echo "NOT_FOUND"'
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and 'FOUND' in result.stdout:
            return True, None
        elif result.returncode == 0 and 'NOT_FOUND' in result.stdout:
            return False, "Public key not found in authorized_keys"
        else:
            # SSH connection failed - key might not be set up
            return False, f"SSH connection failed (return code: {result.returncode})"
    except subprocess.TimeoutExpired:
        return False, "SSH connection timeout"
    except Exception as e:
        return False, f"Error: {str(e)}"


def get_host_key_from_known_hosts(host_ip, known_hosts_path):
    """Check if host key exists in known_hosts file using ssh-keygen -F."""
    if not os.path.exists(known_hosts_path):
        return False
    
    try:
        # Use ssh-keygen -F to check if host is in known_hosts
        # This works with both hashed and unhashed entries
        cmd = ['ssh-keygen', '-F', host_ip, '-f', known_hosts_path]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # ssh-keygen -F returns 0 if host is found, 1 if not found
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        print(f"  WARNING: Could not check known_hosts for {host_ip}: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Verify SSH configuration for Ansible access',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--user',
        required=True,
        help='SSH username to use for connections'
    )
    parser.add_argument(
        '--key',
        required=True,
        help='Path to private SSH key (e.g., ~/.ssh/gcp_rke2_key)'
    )
    parser.add_argument(
        '--inventory',
        default='inventory.yml',
        help='Path to Ansible inventory file (default: inventory.yml)'
    )
    
    args = parser.parse_args()
    
    # Expand user home directory
    private_key_path = os.path.expanduser(args.key)
    known_hosts_path = os.path.expanduser(f'~{args.user}/.ssh/known_hosts')
    
    # Validate private key exists
    if not os.path.exists(private_key_path):
        print(f"ERROR: Private key file not found: {private_key_path}", file=sys.stderr)
        sys.exit(1)
    
    # Load inventory
    print(f"Loading inventory from {args.inventory}...")
    inventory = load_inventory(args.inventory)
    
    # Get target hosts
    target_hosts = get_target_hosts(inventory)
    if not target_hosts:
        print("ERROR: No master or worker nodes found in inventory", file=sys.stderr)
        sys.exit(1)
    
    print(f"Found {len(target_hosts)} target hosts:")
    for host in target_hosts:
        print(f"  - {host['name']} ({host['type']}): {host['ip']}")
    
    # Get public key
    print(f"\nExtracting public key from {private_key_path}...")
    public_key = get_public_key_from_private(private_key_path)
    if not public_key:
        sys.exit(1)
    
    print(f"Public key fingerprint: {public_key.split()[1] if len(public_key.split()) > 1 else 'N/A'}")
    
    # Check 1: Public key in authorized_keys on all target hosts
    print("\n" + "="*70)
    print("CHECK 1: Verifying public key in authorized_keys on target hosts")
    print("="*70)
    
    authorized_keys_ok = True
    failed_hosts = []
    
    for host in target_hosts:
        print(f"Checking {host['name']} ({host['ip']})...", end=' ')
        found, error_msg = check_public_key_in_authorized_keys(host['ip'], args.user, public_key, private_key_path)
        if found:
            print("✓ Public key found in authorized_keys")
        else:
            print(f"✗ {error_msg or 'Public key NOT found in authorized_keys'}")
            authorized_keys_ok = False
            failed_hosts.append({'host': host, 'error': error_msg})
    
    # Check 2: Host keys in known_hosts on bastion
    print("\n" + "="*70)
    print("CHECK 2: Verifying host keys in known_hosts on bastion host")
    print("="*70)
    
    known_hosts_ok = True
    missing_host_keys = []
    
    print(f"Checking known_hosts file: {known_hosts_path}")
    
    for host in target_hosts:
        print(f"Checking {host['name']} ({host['ip']})...", end=' ')
        if get_host_key_from_known_hosts(host['ip'], known_hosts_path):
            print("✓ Host key found in known_hosts")
        else:
            print("✗ Host key NOT found in known_hosts")
            known_hosts_ok = False
            missing_host_keys.append(host)
    
    # Final result
    print("\n" + "="*70)
    print("VERIFICATION RESULT")
    print("="*70)
    
    if authorized_keys_ok and known_hosts_ok:
        print("✓ SSH configuration is COMPLETE")
        print("\nAll checks passed:")
        print(f"  ✓ Public key is in authorized_keys on all {len(target_hosts)} target hosts")
        print(f"  ✓ All {len(target_hosts)} host keys are in known_hosts")
        sys.exit(0)
    else:
        print("✗ SSH configuration is INCOMPLETE")
        print("\nIssues found:")
        
        if not authorized_keys_ok:
            print(f"\n  ✗ Public key issue on {len(failed_hosts)} host(s):")
            for item in failed_hosts:
                host = item['host']
                error = item.get('error', '')
                print(f"      - {host['name']} ({host['ip']}): {error}")
            print(f"\n    To fix, run on bastion host for each target:")
            print(f"      ssh-copy-id -i {private_key_path}.pub {args.user}@<host_ip>")
            print(f"    Or manually copy the public key content to ~/.ssh/authorized_keys on each target host")
            print(f"    Public key content:")
            print(f"      {public_key}")
        
        if not known_hosts_ok:
            print(f"\n  ✗ Host keys missing in known_hosts for {len(missing_host_keys)} host(s):")
            for host in missing_host_keys:
                print(f"      - {host['name']} ({host['ip']})")
            print(f"\n    To fix, run on bastion host:")
            print(f"      ssh-keyscan -H <host_ip> >> {known_hosts_path}")
            print(f"    Or for all hosts at once:")
            host_ips = ' '.join([h['ip'] for h in missing_host_keys])
            print(f"      ssh-keyscan -H {host_ips} >> {known_hosts_path}")
        
        sys.exit(1)


if __name__ == '__main__':
    main()

