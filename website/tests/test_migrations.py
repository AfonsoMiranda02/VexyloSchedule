from django.test import TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from datetime import time


class MigrationExecutorTests(TransactionTestCase):
    """
    Testes de consistência de migrações utilizando MigrationExecutor:
    Garante que a transição de migrações anteriores (0004/0005) para a mais recente (0007)
    ocorre sem perdas, sem erros de integridade e sem sobrescrever escolhas explícitas do administrador.
    """
    migrate_from = [('website', '0005_remove_businessinfo_business_cancel_limit_positive_and_more')]
    migrate_to = [('website', '0007_preserve_opening_hours_admin_choices')]

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.loader.build_graph()

    def tearDown(self):
        # Garante sempre que o estado da BD é restaurado para a migração mais recente
        self.executor.loader.build_graph()
        targets = self.executor.loader.graph.leaf_nodes('website')
        self.executor.migrate(targets)
        self.executor.loader.build_graph()
        super().tearDown()

    def test_migration_0005_to_latest_preserves_custom_admin_choices(self):
        # 1. Reverter para 0005
        self.executor.migrate(self.migrate_from)
        self.executor.loader.build_graph()
        old_apps = self.executor.loader.project_state(self.migrate_from).apps
        OldBusinessInfo = old_apps.get_model('website', 'BusinessInfo')
        OldOpeningHours = old_apps.get_model('website', 'BusinessOpeningHours')

        biz = OldBusinessInfo.objects.create(name="Mig Test Salon", phone="911222333", schedule="H")
        # Administrador configurou expressamente quarta-feira (2) como aberta
        wed = OldOpeningHours.objects.create(
            business=biz, weekday=2, is_open=True,
            opening_time=time(9, 0), closing_time=time(18, 0)
        )

        # 2. Aplicar migrações progressivamente até 0007 (mais recente)
        self.executor.loader.build_graph()
        self.executor.migrate(self.migrate_to)
        self.executor.loader.build_graph()

        new_apps = self.executor.loader.project_state(self.migrate_to).apps
        NewOpeningHours = new_apps.get_model('website', 'BusinessOpeningHours')
        wed_fresh = NewOpeningHours.objects.get(id=wed.id)
        self.assertTrue(wed_fresh.is_open, "A migração 0007 não pode sobrescrever a decisão do admin de manter quarta-feira aberta.")

    def test_migration_0004_to_latest_clean_apply(self):
        # 1. Reverter para 0004
        self.executor.migrate([('website', '0004_backfill_snapshots_and_hours')])
        self.executor.loader.build_graph()

        # 2. Aplicar migrações até 0007
        self.executor.migrate(self.migrate_to)
        self.executor.loader.build_graph()

        new_apps = self.executor.loader.project_state(self.migrate_to).apps
        NewOpeningHours = new_apps.get_model('website', 'BusinessOpeningHours')
        self.assertIsNotNone(NewOpeningHours.objects.all())
