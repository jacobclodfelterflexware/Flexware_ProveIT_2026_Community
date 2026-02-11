import mqtt, { MqttClient } from 'mqtt';

export interface MqttMessage {
  topic: string;
  payload: string;
  timestamp: number;
}

export interface MqttClientConfig {
  brokerUrl: string;
  username?: string;
  password?: string;
  clientId?: string;
}

export class MqttTopicClient {
  private client: MqttClient | null = null;
  private messageHandlers: Set<(message: MqttMessage) => void> = new Set();
  private connectionHandlers: Set<(connected: boolean) => void> = new Set();
  private config: MqttClientConfig;
  private isConnected: boolean = false;

  constructor(config: MqttClientConfig) {
    this.config = {
      ...config,
      clientId: config.clientId || `mqtt-topic-tree-${Math.random().toString(16).substring(2, 10)}`,
    };
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.client = mqtt.connect(this.config.brokerUrl, {
          clientId: this.config.clientId,
          username: this.config.username,
          password: this.config.password,
          clean: true,
          reconnectPeriod: 5000,
          connectTimeout: 30000,
        });

        this.client.on('connect', () => {
          console.log('[MQTT] Connected to broker');
          this.isConnected = true;
          this.notifyConnectionHandlers(true);

          // Subscribe to all topics
          this.client?.subscribe('#', { qos: 0 }, (err) => {
            if (err) {
              console.error('[MQTT] Subscription error:', err);
              reject(err);
            } else {
              console.log('[MQTT] Subscribed to all topics (#)');
              resolve();
            }
          });
        });

        this.client.on('message', (topic: string, payload: Buffer) => {
          const message: MqttMessage = {
            topic,
            payload: payload.toString(),
            timestamp: Date.now(),
          };
          this.notifyMessageHandlers(message);
        });

        this.client.on('error', (error) => {
          console.error('[MQTT] Connection error:', error);
          reject(error);
        });

        this.client.on('close', () => {
          console.log('[MQTT] Connection closed');
          this.isConnected = false;
          this.notifyConnectionHandlers(false);
        });

        this.client.on('offline', () => {
          console.log('[MQTT] Client offline');
          this.isConnected = false;
          this.notifyConnectionHandlers(false);
        });

        this.client.on('reconnect', () => {
          console.log('[MQTT] Attempting to reconnect...');
        });

      } catch (error) {
        reject(error);
      }
    });
  }

  onMessage(handler: (message: MqttMessage) => void): () => void {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  onConnectionChange(handler: (connected: boolean) => void): () => void {
    this.connectionHandlers.add(handler);
    // Immediately notify of current state
    handler(this.isConnected);
    return () => this.connectionHandlers.delete(handler);
  }

  private notifyMessageHandlers(message: MqttMessage): void {
    this.messageHandlers.forEach(handler => {
      try {
        handler(message);
      } catch (error) {
        console.error('[MQTT] Error in message handler:', error);
      }
    });
  }

  private notifyConnectionHandlers(connected: boolean): void {
    this.connectionHandlers.forEach(handler => {
      try {
        handler(connected);
      } catch (error) {
        console.error('[MQTT] Error in connection handler:', error);
      }
    });
  }

  disconnect(): void {
    if (this.client) {
      this.client.end(true);
      this.client = null;
      this.isConnected = false;
    }
  }

  getConnectionStatus(): boolean {
    return this.isConnected;
  }
}
