# Copyright 2020-present ScyllaDB
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Tests for accessing alternator-only system tables (from Scylla).

import pytest
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

internal_prefix = '.scylla.alternator.'

# Test that fetching key columns from system tables works
def test_fetch_from_system_tables(scylla_only, dynamodb):
    client = dynamodb.meta.client
    tables_response = client.scan(
        TableName=f'{internal_prefix}system_schema.tables',
        AttributesToGet=['keyspace_name', 'table_name'],
    )


    for item in tables_response['Items']:
        ks_name = item['keyspace_name']
        table_name = item['table_name']

        if 'system' not in ks_name:
            continue

        col_response = client.query(
            TableName=f'{internal_prefix}system_schema.columns',
            KeyConditionExpression=Key('keyspace_name').eq(ks_name)
            & Key('table_name').eq(table_name),
        )


        key_columns = [
            item['column_name']
            for item in col_response['Items']
            if item['kind'] in ['clustering', 'partition_key']
        ]

        qualified_name = f"{internal_prefix}{ks_name}.{table_name}"
        import time
        start = time.time()
        response = client.scan(TableName=qualified_name, AttributesToGet=key_columns, Limit=50)
        print(ks_name, table_name, len(str(response)), time.time()-start)

def test_block_access_to_non_system_tables_with_virtual_interface(scylla_only, test_table_s, dynamodb):
    client = dynamodb.meta.client
    with pytest.raises(ClientError, match=f'ResourceNotFoundException.*{internal_prefix}'):
        tables_response = client.scan(
            TableName=f"{internal_prefix}alternator_{test_table_s.name}.{test_table_s.name}"
        )

def test_block_creating_tables_with_reserved_prefix(scylla_only, dynamodb):
    client = dynamodb.meta.client
    for wrong_name_postfix in ['', 'a', 'xxx', 'system_auth.roles', 'table_name']:
        with pytest.raises(ClientError, match=internal_prefix):
            dynamodb.create_table(TableName=internal_prefix+wrong_name_postfix,
                    BillingMode='PAY_PER_REQUEST',
                    KeySchema=[{'AttributeName':'p', 'KeyType':'HASH'}],
                    AttributeDefinitions=[{'AttributeName':'p', 'AttributeType': 'S'}]
            )

