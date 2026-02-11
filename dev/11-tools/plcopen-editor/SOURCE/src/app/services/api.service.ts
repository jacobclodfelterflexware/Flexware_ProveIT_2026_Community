/**
 * API Service for PLCopen XML backend
 */
import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface StoredProject {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectListResponse {
  projects: StoredProject[];
}

export interface SaveProjectResponse {
  success: boolean;
  message: string;
  project?: StoredProject;
}

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  // API base URL - relative to current host
  private apiUrl = '/api/plcopen';

  constructor(private http: HttpClient) {}

  /**
   * Get list of all stored projects
   */
  listProjects(): Observable<ProjectListResponse> {
    return this.http.get<ProjectListResponse>(`${this.apiUrl}/projects`);
  }

  /**
   * Get a project's XML content by ID
   */
  getProject(projectId: string): Observable<string> {
    return this.http.get(`${this.apiUrl}/projects/${projectId}`, {
      responseType: 'text'
    });
  }

  /**
   * Save a project to the server
   */
  saveProject(name: string, xmlContent: string): Observable<SaveProjectResponse> {
    return this.http.post<SaveProjectResponse>(`${this.apiUrl}/projects`, {
      name: name,
      xml_content: xmlContent
    });
  }

  /**
   * Delete a project by ID
   */
  deleteProject(projectId: string): Observable<any> {
    return this.http.delete(`${this.apiUrl}/projects/${projectId}`);
  }

  /**
   * Validate PLCopen XML
   */
  validateXml(xmlContent: string): Observable<any> {
    const headers = new HttpHeaders({ 'Content-Type': 'application/xml' });
    return this.http.post(`${this.apiUrl}/validate`, xmlContent, { headers });
  }

  /**
   * Import and parse PLCopen XML
   */
  importXml(xmlContent: string): Observable<any> {
    const headers = new HttpHeaders({ 'Content-Type': 'application/xml' });
    return this.http.post(`${this.apiUrl}/import`, xmlContent, { headers });
  }
}
