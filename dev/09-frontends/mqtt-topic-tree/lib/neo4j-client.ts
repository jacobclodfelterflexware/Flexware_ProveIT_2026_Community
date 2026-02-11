// Neo4j driver singleton for server-side use
import neo4j, { Driver, Session } from 'neo4j-driver';

// Environment-based configuration
const NEO4J_URI = process.env.NEO4J_URI || 'bolt://YOUR_NEO4J_HOST:YOUR_NEO4J_BOLT_PORT';
const NEO4J_USER = process.env.NEO4J_USER || 'YOUR_NEO4J_USERNAME';
const NEO4J_PASSWORD = process.env.NEO4J_PASSWORD || 'password';

// Singleton driver instance
let driver: Driver | null = null;

/**
 * Get or create the Neo4j driver singleton
 */
export function getDriver(): Driver {
  if (!driver) {
    driver = neo4j.driver(
      NEO4J_URI,
      neo4j.auth.basic(NEO4J_USER, NEO4J_PASSWORD),
      {
        maxConnectionPoolSize: 50,
        connectionAcquisitionTimeout: 30000,
      }
    );
    console.log('[Neo4j] Driver initialized:', NEO4J_URI);
  }
  return driver;
}

/**
 * Get a new session from the driver
 */
export function getSession(): Session {
  return getDriver().session();
}

/**
 * Close the driver (for cleanup)
 */
export async function closeDriver(): Promise<void> {
  if (driver) {
    await driver.close();
    driver = null;
    console.log('[Neo4j] Driver closed');
  }
}

/**
 * Verify connectivity to Neo4j
 */
export async function verifyConnectivity(): Promise<boolean> {
  try {
    await getDriver().verifyConnectivity();
    return true;
  } catch (error) {
    console.error('[Neo4j] Connectivity check failed:', error);
    return false;
  }
}
