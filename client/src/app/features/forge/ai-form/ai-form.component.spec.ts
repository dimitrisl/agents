import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { NO_ERRORS_SCHEMA } from '@angular/core';
import { AiFormComponent } from './ai-form.component';

describe('AiFormComponent', () => {
  let component: AiFormComponent;
  let fixture: ComponentFixture<AiFormComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HttpClientTestingModule, RouterTestingModule, AiFormComponent],
      schemas: [NO_ERRORS_SCHEMA]
    }).compileComponents();

    fixture = TestBed.createComponent(AiFormComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('offers Male, Female, and Other alongside AI Choice without Non-binary', () => {
    const select = fixture.nativeElement.querySelector('#ai-gender') as HTMLSelectElement;
    const values = Array.from(select.options).map((o) => o.value);
    expect(values).toEqual(['AI Choice', 'Male', 'Female', 'Other']);
    expect(values).not.toContain('Non-binary');
  });
});
