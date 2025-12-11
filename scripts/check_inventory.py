#!/usr/bin/env python3
"""
Inventory File Validation Script

This script validates the Ansible inventory.yml file:
1. Checks YAML syntax validity
2. Verifies required fields and structure
3. Checks for placeholder values that need to be replaced
4. Validates IP address formats (optional)

Usage:
    python3 check_inventory.py [--inventory <inventory_file>]

Example:
    python3 check_inventory.py
    python3 check_inventory.py --inventory inventory.yml
"""

import argparse
import os
import sys
import yaml
import re
from pathlib import Path
from ipaddress import ip_address, ip_network, AddressValueError


# Placeholder patterns to detect
PLACEHOLDER_PATTERNS = [
    r'<BASTION_IP>',
    r'<MASTER\d+_IP>',
    r'<WORKER\d+_IP>',
    r'<BASTION_HOSTNAME>',
    r'<MASTER\d+_HOSTNAME>',
    r'<WORKER\d+_HOSTNAME>',
    r'<SSH_USER>',
    r'<SSH_KEY_NAME>',
    r'<WORKER\d+_MGMT_IP>',
    r'<WORKER\d+_DATA_IP>',
]

# Required groups
REQUIRED_GROUPS = ['bastion', 'masters', 'workers']

# Required fields for each host type
REQUIRED_HOST_FIELDS = {
    'bastion': ['ansible_host', 'ansible_hostname', 'ansible_user', 
                'ansible_ssh_private_key_file', 'internal_ip'],
    'master': ['ansible_host', 'ansible_hostname', 'ansible_user', 
               'ansible_ssh_private_key_file'],
    'worker': ['ansible_host', 'ansible_hostname', 'ansible_user', 
               'ansible_ssh_private_key_file', 'mgmt_ip', 'prod_data_ip'],
}

# Required vars in all.vars
REQUIRED_VARS = [
    'ansible_python_interpreter',
    'control_vlan_network',
    'control_vlan_gateway',
    'data_vlan_network',
    'data_vlan_gateway',
    'lb_vip_control',
    'lb_vip_data',
]


def load_inventory(inventory_path):
    """Load and parse Ansible inventory YAML file."""
    if not os.path.exists(inventory_path):
        print(f"ERROR: Inventory file not found: {inventory_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(inventory_path, 'r') as f:
            inventory = yaml.safe_load(f)
        return inventory
    except yaml.YAMLError as e:
        print(f"ERROR: Invalid YAML syntax in {inventory_path}: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to load inventory file {inventory_path}: {e}", file=sys.stderr)
        sys.exit(1)


def check_placeholder(value, path=""):
    """Check if a value contains placeholder patterns."""
    if not isinstance(value, str):
        return []
    
    found_placeholders = []
    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, value):
            found_placeholders.append(pattern)
    
    return found_placeholders


def find_placeholders(data, path="", found=None):
    """Recursively find all placeholder values in inventory."""
    if found is None:
        found = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key
            placeholders = check_placeholder(value, current_path)
            if placeholders:
                found.append({
                    'path': current_path,
                    'value': value,
                    'placeholders': placeholders
                })
            else:
                find_placeholders(value, current_path, found)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            current_path = f"{path}[{i}]" if path else f"[{i}]"
            find_placeholders(item, current_path, found)
    
    return found


def validate_ip_address(ip_str):
    """Validate IP address format."""
    try:
        ip_address(ip_str)
        return True
    except (ValueError, AddressValueError):
        return False


def validate_ip_network(network_str):
    """Validate IP network format (CIDR notation)."""
    try:
        ip_network(network_str, strict=False)
        return True
    except (ValueError, AddressValueError):
        return False


def validate_inventory_structure(inventory):
    """Validate inventory structure and required fields."""
    errors = []
    warnings = []
    
    # Check top-level structure
    if 'all' not in inventory:
        errors.append("Missing 'all' section at top level")
        return errors, warnings
    
    all_section = inventory['all']
    
    # Check required vars
    if 'vars' not in all_section:
        errors.append("Missing 'vars' section in 'all'")
    else:
        vars_section = all_section['vars']
        for var in REQUIRED_VARS:
            if var not in vars_section:
                errors.append(f"Missing required variable: {var}")
    
    # Check required groups
    if 'children' not in all_section:
        errors.append("Missing 'children' section in 'all'")
        return errors, warnings
    
    children = all_section['children']
    
    for group in REQUIRED_GROUPS:
        if group not in children:
            errors.append(f"Missing required group: {group}")
            continue
        
        group_section = children[group]
        
        # Check hosts
        if 'hosts' not in group_section:
            errors.append(f"Missing 'hosts' section in group '{group}'")
            continue
        
        hosts = group_section['hosts']
        
        if not hosts:
            warnings.append(f"Group '{group}' has no hosts defined")
            continue
        
        # Validate each host
        for host_name, host_vars in hosts.items():
            if group == 'bastion':
                host_type = 'bastion'
            elif group == 'masters':
                host_type = 'master'
            elif group == 'workers':
                host_type = 'worker'
            else:
                continue
            
            required_fields = REQUIRED_HOST_FIELDS.get(host_type, [])
            for field in required_fields:
                if field not in host_vars:
                    errors.append(f"Host '{host_name}' ({group}) missing required field: {field}")
    
    return errors, warnings


def validate_ip_addresses(inventory):
    """Validate IP address formats in inventory."""
    errors = []
    warnings = []
    
    all_section = inventory.get('all', {})
    children = all_section.get('children', {})
    
    # Validate network vars
    network_vars = ['control_vlan_network', 'data_vlan_network']
    vars_section = all_section.get('vars', {})
    for var in network_vars:
        if var in vars_section:
            value = vars_section[var]
            if isinstance(value, str) and not validate_ip_network(value):
                errors.append(f"Invalid network format in {var}: {value}")
    
    # Validate gateway and VIP vars
    ip_vars = ['control_vlan_gateway', 'data_vlan_gateway', 'lb_vip_control', 'lb_vip_data']
    for var in ip_vars:
        if var in vars_section:
            value = vars_section[var]
            if isinstance(value, str) and not validate_ip_address(value):
                errors.append(f"Invalid IP address format in {var}: {value}")
    
    # Validate host IPs
    for group_name, group_section in children.items():
        if 'hosts' not in group_section:
            continue
        
        for host_name, host_vars in group_section['hosts'].items():
            # Check ansible_host
            if 'ansible_host' in host_vars:
                ip = host_vars['ansible_host']
                if isinstance(ip, str) and not validate_ip_address(ip):
                    errors.append(f"Invalid IP address in {host_name}.ansible_host: {ip}")
            
            # Check internal_ip (bastion)
            if 'internal_ip' in host_vars:
                ip = host_vars['internal_ip']
                if isinstance(ip, str) and not validate_ip_address(ip):
                    errors.append(f"Invalid IP address in {host_name}.internal_ip: {ip}")
            
            # Check mgmt_ip and prod_data_ip (workers)
            for ip_field in ['mgmt_ip', 'prod_data_ip']:
                if ip_field in host_vars:
                    ip = host_vars[ip_field]
                    if isinstance(ip, str) and not validate_ip_address(ip):
                        errors.append(f"Invalid IP address in {host_name}.{ip_field}: {ip}")
    
    return errors, warnings


def main():
    parser = argparse.ArgumentParser(
        description='Validate Ansible inventory.yml file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--inventory',
        default='inventory.yml',
        help='Path to inventory file (default: inventory.yml)'
    )
    
    args = parser.parse_args()
    
    print(f"Validating inventory file: {args.inventory}")
    print("-" * 60)
    
    # Load inventory
    try:
        inventory = load_inventory(args.inventory)
        print("✓ YAML syntax is valid")
    except SystemExit:
        sys.exit(1)
    
    # Check structure
    structure_errors, structure_warnings = validate_inventory_structure(inventory)
    
    if structure_errors:
        print("\n✗ Structure validation failed:")
        for error in structure_errors:
            print(f"  ERROR: {error}")
    else:
        print("✓ Inventory structure is valid")
    
    if structure_warnings:
        print("\n⚠ Warnings:")
        for warning in structure_warnings:
            print(f"  WARNING: {warning}")
    
    # Check for placeholders
    placeholders = find_placeholders(inventory)
    
    if placeholders:
        print("\n⚠ Found placeholder values that need to be replaced:")
        for item in placeholders:
            print(f"  {item['path']}: {item['value']}")
        print("\n  Please replace all placeholder values with actual values.")
    else:
        print("✓ No placeholder values found")
    
    # Validate IP addresses (only if no placeholders found)
    if not placeholders:
        ip_errors, ip_warnings = validate_ip_addresses(inventory)
        
        if ip_errors:
            print("\n✗ IP address validation failed:")
            for error in ip_errors:
                print(f"  ERROR: {error}")
        else:
            print("✓ IP address formats are valid")
        
        if ip_warnings:
            print("\n⚠ IP validation warnings:")
            for warning in ip_warnings:
                print(f"  WARNING: {warning}")
    
    # Summary
    print("\n" + "-" * 60)
    total_errors = len(structure_errors)
    if not placeholders:
        ip_errors, _ = validate_ip_addresses(inventory)
        total_errors += len(ip_errors)
    
    if total_errors == 0 and not placeholders:
        print("✓ Inventory file is valid and ready to use!")
        sys.exit(0)
    elif placeholders:
        print("⚠ Inventory file has placeholder values that need to be replaced.")
        sys.exit(1)
    else:
        print(f"✗ Inventory file has {total_errors} error(s) that need to be fixed.")
        sys.exit(1)


if __name__ == '__main__':
    main()

