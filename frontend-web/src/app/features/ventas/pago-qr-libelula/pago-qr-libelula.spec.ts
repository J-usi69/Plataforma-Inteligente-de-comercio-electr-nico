import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Subject, of } from 'rxjs';
import { QrLibelula } from '../../../core/models/user.model';
import { BusinessService } from '../../../core/services/business.service';
import { PagoQrLibelula } from './pago-qr-libelula';

describe('PagoQrLibelula', () => {
  const qr: QrLibelula = {
    pago_id: 1,
    transaccion_id: 'PRUEBA-1',
    qr_url: 'data:image/png;base64,AAAA',
    url_pasarela: null,
    monto: 89.9,
    modo_prueba: true,
  };
  let respuestaQr: Subject<QrLibelula>;
  let business: {
    generarQrLibelula: ReturnType<typeof vi.fn>;
    getEstadoQrLibelula: ReturnType<typeof vi.fn>;
    simularPagoQrLibelula: ReturnType<typeof vi.fn>;
  };
  let fixture: ComponentFixture<PagoQrLibelula>;

  beforeEach(async () => {
    vi.useFakeTimers();
    // El QR llega cuando el test lo decide, como una respuesta lenta del backend
    respuestaQr = new Subject<QrLibelula>();
    business = {
      generarQrLibelula: vi.fn(() => respuestaQr),
      getEstadoQrLibelula: vi.fn(() => of({ pagado: false, estado_venta: 'pendiente', modo_prueba: true })),
      simularPagoQrLibelula: vi.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [PagoQrLibelula],
      providers: [{ provide: BusinessService, useValue: business }],
    }).compileComponents();

    fixture = TestBed.createComponent(PagoQrLibelula);
    fixture.componentRef.setInput('ventaId', 131);
    fixture.detectChanges(); // ngOnInit pide el QR
  });

  afterEach(() => vi.useRealTimers());

  it('consulta cada 4 segundos y avisa una sola vez cuando se paga', () => {
    const pagado = vi.fn();
    fixture.componentInstance.pagado.subscribe(pagado);
    respuestaQr.next(qr);

    vi.advanceTimersByTime(4000);
    expect(business.getEstadoQrLibelula).toHaveBeenCalledTimes(1);
    expect(pagado).not.toHaveBeenCalled();

    business.getEstadoQrLibelula.mockReturnValue(of({ pagado: true, estado_venta: 'pagada', modo_prueba: true }));
    vi.advanceTimersByTime(4000);
    expect(pagado).toHaveBeenCalledTimes(1);

    // Ya pagado deja de consultar
    vi.advanceTimersByTime(20000);
    expect(business.getEstadoQrLibelula).toHaveBeenCalledTimes(2);
  });

  it('si se cierra mientras el QR se genera, no deja consultas corriendo', () => {
    fixture.destroy();
    respuestaQr.next(qr);

    vi.advanceTimersByTime(20000);
    expect(business.getEstadoQrLibelula).not.toHaveBeenCalled();
  });
});
