import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import {
  ForgeBadgeComponent,
  ForgePageComponent,
  ForgeSectionComponent,
  ForgeStatBoxComponent,
} from '../../shared/ui';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [
    CommonModule,
    ForgeBadgeComponent,
    ForgePageComponent,
    ForgeSectionComponent,
    ForgeStatBoxComponent,
  ],
  templateUrl: './admin.component.html',
  styleUrl: './admin.component.css',
})
export class AdminComponent implements OnInit {
  totalCharacters = 0;

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.http.get<any[]>(`${environment.apiBaseUrl}/characters/`).subscribe((chars) => {
      this.totalCharacters = chars ? chars.length : 0;
    });
  }
}
