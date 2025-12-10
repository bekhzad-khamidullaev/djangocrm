#!/usr/bin/env python
"""
Quick setup script for SMS and VoIP providers
Run: python setup_providers.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webcrm.settings')
django.setup()

from integrations.models import ChannelAccount
from voip.models import OnlinePBXSettings


def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")


def print_success(text):
    """Print success message"""
    print(f"✅ {text}")


def print_error(text):
    """Print error message"""
    print(f"❌ {text}")


def print_info(text):
    """Print info message"""
    print(f"ℹ️  {text}")


def setup_eskiz_sms():
    """Setup Eskiz SMS provider"""
    print_header("Eskiz SMS Configuration")
    
    print("Please enter your Eskiz SMS credentials:")
    print("(Get them from: https://eskiz.uz)\n")
    
    email = input("Eskiz Email: ").strip()
    password = input("Eskiz Password: ").strip()
    from_name = input("Sender ID (e.g., 4546): ").strip() or "4546"
    
    if not email or not password:
        print_error("Email and password are required!")
        return False
    
    try:
        # Test authentication
        from integrations.sms import eskiz_auth
        print_info("Testing authentication...")
        token = eskiz_auth(email, password)
        
        if not token:
            print_error("Authentication failed! Please check your credentials.")
            return False
        
        print_success("Authentication successful!")
        
        # Create or update provider
        provider, created = ChannelAccount.objects.update_or_create(
            type='eskiz',
            defaults={
                'name': 'Eskiz SMS Provider',
                'is_active': True,
                'eskiz_email': email,
                'eskiz_password': password,
                'eskiz_from': from_name,
                'eskiz_token': token,
            }
        )
        
        if created:
            print_success(f"Eskiz provider created (ID: {provider.id})")
        else:
            print_success(f"Eskiz provider updated (ID: {provider.id})")
        
        # Test sending SMS
        test_sms = input("\nWould you like to send a test SMS? (y/n): ").strip().lower()
        if test_sms == 'y':
            phone = input("Enter phone number (e.g., +998901234567): ").strip()
            if phone:
                from integrations.sms import eskiz_send_sms
                ok, provider_id, raw = eskiz_send_sms(token, from_name, phone, "Test SMS from Django CRM")
                if ok:
                    print_success(f"Test SMS sent successfully! Provider ID: {provider_id}")
                else:
                    print_error(f"Test SMS failed: {raw}")
        
        return True
        
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False


def setup_playmobile_sms():
    """Setup PlayMobile SMS provider"""
    print_header("PlayMobile SMS Configuration")
    
    print("Please select authentication method:")
    print("1. Token Authentication (Recommended)")
    print("2. Login/Password Authentication")
    
    auth_choice = input("\nChoice (1 or 2): ").strip()
    
    if auth_choice == '1':
        auth_type = 'token'
        print("\nPlease enter your PlayMobile credentials:")
        token = input("Bearer Token: ").strip()
        api_url = input("API URL (default: https://api.playmobile.uz/v1/messages): ").strip()
        api_url = api_url or "https://api.playmobile.uz/v1/messages"
        from_name = input("Sender ID: ").strip()
        
        if not token or not from_name:
            print_error("Token and Sender ID are required!")
            return False
        
        try:
            provider, created = ChannelAccount.objects.update_or_create(
                type='playmobile',
                defaults={
                    'name': 'PlayMobile SMS Provider',
                    'is_active': True,
                    'playmobile_auth_type': 'token',
                    'playmobile_token': token,
                    'playmobile_from': from_name,
                    'playmobile_api_url': api_url,
                }
            )
            
            if created:
                print_success(f"PlayMobile provider created (ID: {provider.id})")
            else:
                print_success(f"PlayMobile provider updated (ID: {provider.id})")
            
            return True
            
        except Exception as e:
            print_error(f"Error: {str(e)}")
            return False
    
    elif auth_choice == '2':
        auth_type = 'basic'
        print("\nPlease enter your PlayMobile credentials:")
        login = input("Login: ").strip()
        password = input("Password: ").strip()
        api_url = input("API URL (default: https://send.smsxabar.uz/api/v1/send): ").strip()
        api_url = api_url or "https://send.smsxabar.uz/api/v1/send"
        from_name = input("Sender ID: ").strip()
        
        if not login or not password or not from_name:
            print_error("Login, password, and Sender ID are required!")
            return False
        
        try:
            provider, created = ChannelAccount.objects.update_or_create(
                type='playmobile',
                defaults={
                    'name': 'PlayMobile SMS Provider',
                    'is_active': True,
                    'playmobile_auth_type': 'basic',
                    'playmobile_login': login,
                    'playmobile_password': password,
                    'playmobile_from': from_name,
                    'playmobile_api_url': api_url,
                }
            )
            
            if created:
                print_success(f"PlayMobile provider created (ID: {provider.id})")
            else:
                print_success(f"PlayMobile provider updated (ID: {provider.id})")
            
            return True
            
        except Exception as e:
            print_error(f"Error: {str(e)}")
            return False
    
    else:
        print_error("Invalid choice!")
        return False


def setup_asterisk_ami():
    """Setup Asterisk AMI configuration"""
    print_header("Asterisk AMI Configuration")
    
    print("Please enter your Asterisk AMI credentials:")
    print("(Configure AMI on your Asterisk server first)\n")
    
    host = input("Asterisk Host (IP or hostname): ").strip()
    port = input("AMI Port (default: 5038): ").strip() or "5038"
    username = input("AMI Username: ").strip()
    secret = input("AMI Secret: ").strip()
    
    if not host or not username or not secret:
        print_error("Host, username, and secret are required!")
        return False
    
    print_info("\nAdd these settings to your webcrm/settings.py or .env file:")
    print("\n# Asterisk AMI Configuration")
    print(f"ASTERISK_AMI = {{")
    print(f"    'HOST': '{host}',")
    print(f"    'PORT': {port},")
    print(f"    'USERNAME': '{username}',")
    print(f"    'SECRET': '{secret}',")
    print(f"    'USE_SSL': False,")
    print(f"    'CONNECT_TIMEOUT': 5,")
    print(f"    'RECONNECT_DELAY': 5,")
    print(f"}}")
    print(f"\nVOIP = [")
    print(f"    {{'PROVIDER': 'asterisk', 'ENABLED': True}}")
    print(f"]")
    print(f"\nDEFAULT_CALLER_ID = '1000'  # Your extension number")
    
    # Test connection
    test = input("\nWould you like to test the connection? (y/n): ").strip().lower()
    if test == 'y':
        try:
            from voip.integrations.asterisk import AsteriskAMI
            
            print_info("Testing connection...")
            ami = AsteriskAMI(
                host=host,
                port=int(port),
                username=username,
                secret=secret
            )
            
            if ami.connect():
                print_success("Successfully connected to Asterisk AMI!")
                response = ami.command('core show version')
                print(f"\nAsterisk Version:\n{response}")
                ami.disconnect()
                return True
            else:
                print_error("Failed to connect to Asterisk AMI")
                return False
                
        except Exception as e:
            print_error(f"Connection test failed: {str(e)}")
            return False
    
    return True


def setup_onlinepbx():
    """Setup OnlinePBX configuration"""
    print_header("OnlinePBX Configuration")
    
    print("Please enter your OnlinePBX credentials:")
    print("(Get them from: https://onlinepbx.ru)\n")
    
    domain = input("OnlinePBX Domain (e.g., yourcompany.onpbx.ru): ").strip()
    key_id = input("Key ID: ").strip()
    secret_key = input("Secret Key: ").strip()
    api_key = input("API Key: ").strip()
    
    if not domain or not key_id or not secret_key:
        print_error("Domain, Key ID, and Secret Key are required!")
        return False
    
    try:
        settings, created = OnlinePBXSettings.objects.get_or_create(pk=1)
        settings.domain = domain
        settings.key_id = key_id
        settings.key = secret_key
        settings.api_key = api_key
        settings.base_url = 'https://api2.onlinepbx.ru'
        settings.save()
        
        if created:
            print_success("OnlinePBX settings created")
        else:
            print_success("OnlinePBX settings updated")
        
        print_info("\nAdd these settings to your webcrm/settings.py:")
        print(f"\nVOIP = [")
        print(f"    {{'PROVIDER': 'onlinepbx', 'ENABLED': True}}")
        print(f"]")
        
        return True
        
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False


def setup_freeswitch():
    """Setup FreeSWITCH ESL configuration"""
    print_header("FreeSWITCH ESL Configuration")
    
    print("Please enter your FreeSWITCH ESL credentials:")
    print("(Configure ESL on your FreeSWITCH server first)\n")
    
    host = input("FreeSWITCH Host (IP or hostname): ").strip()
    port = input("ESL Port (default: 8021): ").strip() or "8021"
    password = input("ESL Password: ").strip()
    
    if not host or not password:
        print_error("Host and password are required!")
        return False
    
    print_info("\nAdd these settings to your webcrm/settings.py or .env file:")
    print("\n# FreeSWITCH ESL Configuration")
    print(f"FREESWITCH_ESL = {{")
    print(f"    'HOST': '{host}',")
    print(f"    'PORT': {port},")
    print(f"    'PASSWORD': '{password}',")
    print(f"}}")
    print(f"\nVOIP = [")
    print(f"    {{'PROVIDER': 'freeswitch', 'ENABLED': True}}")
    print(f"]")
    
    return True


def main():
    """Main setup wizard"""
    print_header("Django-CRM Provider Setup Wizard")
    
    print("This wizard will help you configure SMS and VoIP providers.\n")
    
    while True:
        print("\nSelect provider to configure:")
        print("1. Eskiz SMS (Uzbekistan)")
        print("2. PlayMobile SMS (Uzbekistan)")
        print("3. Asterisk AMI (VoIP)")
        print("4. OnlinePBX (VoIP)")
        print("5. FreeSWITCH ESL (VoIP)")
        print("6. View configured providers")
        print("0. Exit")
        
        choice = input("\nChoice: ").strip()
        
        if choice == '1':
            setup_eskiz_sms()
        elif choice == '2':
            setup_playmobile_sms()
        elif choice == '3':
            setup_asterisk_ami()
        elif choice == '4':
            setup_onlinepbx()
        elif choice == '5':
            setup_freeswitch()
        elif choice == '6':
            print_header("Configured Providers")
            
            # SMS Providers
            sms_providers = ChannelAccount.objects.filter(
                type__in=['eskiz', 'playmobile'],
                is_active=True
            )
            
            if sms_providers.exists():
                print("SMS Providers:")
                for p in sms_providers:
                    print(f"  • {p.name} (ID: {p.id}) - Type: {p.get_type_display()}")
            else:
                print("No SMS providers configured")
            
            # VoIP Providers
            print("\nVoIP Providers:")
            from django.conf import settings
            voip_config = getattr(settings, 'VOIP', [])
            if voip_config:
                for config in voip_config:
                    enabled = "✓" if config.get('ENABLED') else "✗"
                    print(f"  {enabled} {config.get('PROVIDER', 'Unknown')}")
            else:
                print("No VoIP providers configured in settings.py")
            
        elif choice == '0':
            print("\n👋 Setup complete! Check the documentation for next steps.")
            break
        else:
            print_error("Invalid choice!")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Setup cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        sys.exit(1)
