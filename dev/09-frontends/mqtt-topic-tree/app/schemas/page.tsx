import SchemaLibrary from '@/components/schemas/SchemaLibrary';

export const metadata = {
  title: 'Schema Library - MQTT Topic Tree',
  description: 'Manage schema proposals and topic bindings',
};

export default function SchemasPage() {
  return <SchemaLibrary />;
}
