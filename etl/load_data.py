from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider

auth_provider = PlainTextAuthProvider(
    username= 'cassandra', password='TwojeSuperTrudneHaslo123!'
    )

node_ips= ['34.118.23.223']

try:
    cluster = Cluster(node_ips, auth_provider=auth_provider)
    print("Starting Cassandra cluster...")
    session = cluster.connect()
    session.set_keyspace('air_quality')

    session.shutdown()
    print("Cassandra cluster shutdown")
finally:
    print("End of script")