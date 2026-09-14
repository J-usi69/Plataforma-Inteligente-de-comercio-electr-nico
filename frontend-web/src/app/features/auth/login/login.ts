import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './login.html',
  styles: [`
    .split-layout {
      min-height: calc(100vh - 150px);
      display: grid;
      grid-template-columns: 1.1fr 1fr;
      background: #ffffff;
      border-radius: 20px;
      margin: 2rem auto;
      max-width: 1100px;
      overflow: hidden;
      box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.08);
      border: 1px solid #e2e8f0;
    }

    .brand-side {
      background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #312e81 100%);
      color: #ffffff;
      padding: 3.5rem;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      position: relative;
      overflow: hidden;

      &::after {
        content: '';
        position: absolute;
        width: 350px;
        height: 350px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(99, 102, 241, 0.25) 0%, transparent 70%);
        bottom: -50px;
        right: -50px;
        pointer-events: none;
      }
    }

    .feature-list {
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
      margin: 2.5rem 0;

      .feature-item {
        display: flex;
        align-items: flex-start;
        gap: 1rem;

        .feature-icon {
          width: 36px;
          height: 36px;
          border-radius: 10px;
          background: rgba(255, 255, 255, 0.1);
          backdrop-filter: blur(8px);
          display: flex;
          align-items: center;
          justify-content: center;
          color: #a5b4fc;
          flex-shrink: 0;
        }

        .feature-text {
          h4 { color: #ffffff; font-size: 0.95rem; margin-bottom: 0.2rem; }
          p { color: #94a3b8; font-size: 0.82rem; line-height: 1.4; }
        }
      }
    }

    .form-side {
      padding: 3.5rem 3rem;
      display: flex;
      flex-direction: column;
      justify-content: center;
      background: #ffffff;
    }

    .segmented-control {
      display: flex;
      background: #f1f5f9;
      border-radius: 12px;
      padding: 4px;
      margin-bottom: 2rem;

      button {
        flex: 1;
        padding: 0.65rem;
        border: none;
        background: transparent;
        border-radius: 9px;
        font-weight: 700;
        font-size: 0.875rem;
        color: #64748b;
        cursor: pointer;
        transition: all 0.2s;

        &.active {
          background: #ffffff;
          color: #0f172a;
          box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06);
        }
      }
    }

    @media (max-width: 900px) {
      .split-layout {
        grid-template-columns: 1fr;
        margin: 1rem;
      }
      .brand-side { display: none; }
      .form-side { padding: 2.5rem 1.5rem; }
    }
  `],
})
export class Login {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  isRegisterMode = signal(false);
  isLoading = signal(false);
  errorMessage = signal<string | null>(null);
  successMessage = signal<string | null>(null);

  // Login
  loginInput = '';
  passwordInput = '';

  // Register
  regCorreo = '';
  regPassword = '';
  regCelular = '';

  toggleMode(register: boolean) {
    this.isRegisterMode.set(register);
    this.errorMessage.set(null);
    this.successMessage.set(null);
  }

  onLogin() {
    if (!this.loginInput || !this.passwordInput) {
      this.errorMessage.set('Por favor completa todos los campos requeridos.');
      return;
    }

    this.isLoading.set(true);
    this.errorMessage.set(null);

    this.authService.login({ login: this.loginInput, password: this.passwordInput }).subscribe({
      next: (res) => {
        this.isLoading.set(false);
        if (res.usuario.roles.includes('Administrador')) {
          this.router.navigate(['/admin']);
        } else if (res.usuario.roles.includes('Encargado') || res.usuario.personal?.cargo === 'Encargado') {
          this.router.navigate(['/encargado']);
        } else if (res.usuario.roles.includes('Cajero') || res.usuario.personal?.cargo === 'Cajero') {
          this.router.navigate(['/caja']);
        } else if (res.usuario.roles.includes('Proveedor')) {
          this.router.navigate(['/proveedor']);
        } else {
          this.router.navigate(['/catalogo']);
        }
      },
      error: (err) => {
        this.isLoading.set(false);
        const msg = err.error?.detail || 'Error al iniciar sesión. Verifica tus credenciales.';
        this.errorMessage.set(msg);
      },
    });
  }

  onRegister() {
    if (!this.regCorreo || !this.regPassword) {
      this.errorMessage.set('El correo y la contraseña son campos obligatorios.');
      return;
    }

    this.isLoading.set(true);
    this.errorMessage.set(null);

    this.authService.register({
      correo: this.regCorreo,
      password: this.regPassword,
      celular: this.regCelular || undefined,
    }).subscribe({
      next: () => {
        this.isLoading.set(false);
        this.successMessage.set('¡Cuenta creada con éxito! Ya puedes iniciar sesión.');
        this.loginInput = this.regCorreo;
        this.passwordInput = this.regPassword;
        this.isRegisterMode.set(false);
      },
      error: (err) => {
        this.isLoading.set(false);
        const msg = err.error?.detail || 'No se pudo crear la cuenta. Verifica los datos ingresados.';
        this.errorMessage.set(msg);
      },
    });
  }
}
