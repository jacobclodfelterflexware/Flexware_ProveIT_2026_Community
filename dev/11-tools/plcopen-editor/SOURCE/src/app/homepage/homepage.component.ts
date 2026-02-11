import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { ImportService } from '../services/import.service';
import { ProjectService } from '../services/project.service';
import { ApiService, StoredProject } from '../services/api.service';

@Component({
  selector: 'app-homepage',
  templateUrl: './homepage.component.html',
  styleUrls: ['./homepage.component.css']
})
export class HomepageComponent implements OnInit {
  public title = 'PLCopen-Editor';
  public serverProjects: StoredProject[] = [];
  public loadingProjects = false;
  public loadError = '';
  public selectedProjectId = '';

  constructor(
    private importService: ImportService,
    private projectService: ProjectService,
    private apiService: ApiService,
    private router: Router
  ) { }

  ngOnInit(): void {
    this.loadServerProjects();
  }

  loadServerProjects(): void {
    this.loadingProjects = true;
    this.loadError = '';
    this.apiService.listProjects().subscribe({
      next: (response) => {
        this.serverProjects = response.projects;
        this.loadingProjects = false;
      },
      error: (err) => {
        console.error('Failed to load projects:', err);
        this.loadError = 'Failed to load projects from server';
        this.loadingProjects = false;
      }
    });
  }

  loadSelectedProject(): void {
    if (!this.selectedProjectId) {
      alert('Please select a project');
      return;
    }

    this.apiService.getProject(this.selectedProjectId).subscribe({
      next: (xmlContent) => {
        // Parse the XML and load it into the project service
        this.importService.loadXmlString(xmlContent);
        this.router.navigate(['/projectOverview']);
      },
      error: (err) => {
        console.error('Failed to load project:', err);
        alert('Failed to load project from server');
      }
    });
  }

  public closeProjectModal(): void {
    // @ts-ignore
    document.getElementById('openProjectModal').style.display = 'none';
  }

  fileUpload(event: Event): void {
    this.importService.fileUpload(event);
  }

  createProject(data: any): void {
    this.projectService.createNewProject(data.projectName);
  }
}
