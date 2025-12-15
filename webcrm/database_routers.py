# -*- coding: utf-8 -*-
"""
Database routers for Django CRM
"""


class AsteriskDatabaseRouter:
    """
    Router to direct Asterisk Real-time models to the 'asterisk' database
    """
    
    # List of Asterisk Real-time model names (lowercase)
    asterisk_models = {
        'psendpoint',
        'psauth', 
        'psaor',
        'pscontact',
        'psidentify',
        'pstransport',
        'extension',
    }
    
    asterisk_app_label = 'voip'
    
    def db_for_read(self, model, **hints):
        """
        Route read operations for Asterisk models to 'asterisk' database
        """
        if model._meta.app_label == self.asterisk_app_label:
            if model._meta.model_name in self.asterisk_models:
                return 'asterisk'
        return None
    
    def db_for_write(self, model, **hints):
        """
        Route write operations for Asterisk models to 'asterisk' database
        """
        if model._meta.app_label == self.asterisk_app_label:
            if model._meta.model_name in self.asterisk_models:
                return 'asterisk'
        return None
    
    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations between Asterisk models or between non-Asterisk models
        """
        # Both are Asterisk models
        if (obj1._meta.model_name in self.asterisk_models and 
            obj2._meta.model_name in self.asterisk_models):
            return True
        
        # Neither are Asterisk models
        if (obj1._meta.model_name not in self.asterisk_models and 
            obj2._meta.model_name not in self.asterisk_models):
            return None
        
        # One is Asterisk, one is not - allow but don't enforce FK
        # (handled by db_constraint=False in model definition)
        return None
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Ensure Asterisk models only migrate to 'asterisk' database
        """
        if app_label == self.asterisk_app_label and model_name:
            if model_name in self.asterisk_models:
                return db == 'asterisk'
        
        # For non-Asterisk models, don't migrate to asterisk db
        if db == 'asterisk':
            if model_name and model_name not in self.asterisk_models:
                return False
        
        return None
