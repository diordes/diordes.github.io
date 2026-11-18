/**
 * Orientació de barris (no és assessorament). Revisa sempre dades actuals
 * (soroll, turisme, obres, inundabilitat, preu €/m²).
 */
window.PISOS_ZONES = {
  barcelona: {
    bones: [
      "Eixample (Dreta / parts de l’Esquerra consolidada)",
      "Gràcia (zones tranquil·les, lluny de places molt turístiques)",
      "Sant Gervasi – Galvany / Putxet",
      "Poblenou (eixos interiors, no primera línia massificada)",
      "Les Corts (prop de Zona Universitària / Coliseum)",
    ],
    cautela: [
      "Parts del Raval i del Gòtic amb alta pressió turística / soroll nocturn",
      "Algunes zones del Besòs i La Mina (revisar carrer a carrer)",
      "Planta baixa a eixos molt comercials o de festa",
      "Edificis amb cèdula / ITE / aluminosi pendents",
    ],
  },
  madrid: {
    bones: [
      "Chamberí",
      "Salamanca (segons pressupost)",
      "Retiro / Niño Jesús",
      "Chamartín (Hispanoamérica, Nueva España)",
      "Arganzuela regenerada (legazpi / Madrid Río, carrer a carrer)",
    ],
    cautela: [
      "Entorns amb alta densitat d’oci nocturn (centres molt concrets)",
      "Barris amb regeneració incompleta: mira preus de lloguer i rotació",
      "Plantes baixes a grans vies amb contaminació acústica",
    ],
  },
  valencia: {
    bones: [
      "Eixample / Gran Via",
      "El Pla del Real",
      "Benimaclet (segons carrer)",
      "Campanar / Nou Campanar",
      "Extramurs (zones tranquil·les)",
    ],
    cautela: [
      "Primera línia molt turística al Cabanyal / Malvarrosa (soroll, rotació)",
      "Zones amb risc d’inundació històric: consulta mapes municipals",
      "Interiors amb poca llum a illes molt estretes",
    ],
  },
  malaga: {
    bones: [
      "El Limonar / Cerrado de Calderón (segons pressupost)",
      "Teatinos (per perfil universitari / família)",
      "Pedregalejo (fora de la franja més massificada)",
      "Centro regenerat (carrers interiors, no només plaça)",
    ],
    cautela: [
      "Primera línia turística amb llicències turístiques abundants",
      "Urbanitzacions amb despeses de comunitat altes i poca liquiditat",
    ],
  },
  sevilla: {
    bones: [
      "Nervión",
      "Los Remedios",
      "Triana (segons carrer i planta)",
      "Heliópolis / Sevilla Este consolidat",
    ],
    cautela: [
      "Zones amb alta concentració d’apartaments turístics al centre històric",
      "Baixos a eixos de botelló / festa",
    ],
  },
  bilbao: {
    bones: [
      "Abando / Indautxu",
      "Deusto (zones residencials)",
      "Neguri / Getxo (si amplies àrea metropolitana)",
    ],
    cautela: [
      "Habitatges amb humitats estructurals a edificis antics sense rehabilitar",
    ],
  },
  zaragoza: {
    bones: ["Actur", "Universidad", "Delicias regenerada", "Centro (carrers tranquils)"],
    cautela: ["Zones amb molta rotació de lloguer i poc manteniment d’escala"],
  },
  alicante: {
    bones: ["Centro consolidat", "San Juan (segons zona)", "Playa San Juan interior"],
    cautela: ["Primera línia molt turística", "Urbanitzacions amb poca demanda fora de temporada"],
  },
  murcia: {
    bones: ["Vistalegre", "La Flota", "Centro"],
    cautela: ["Revisa aïllament tèrmic i orientació (estius durs)"],
  },
  palma: {
    bones: ["El Terreno (segons carrer)", "Son Armadams", "Portixol / Molinar (no primera línia massificada)"],
    cautela: ["Pressió turística i llicències", "Preus desconnectats de renda local"],
  },
};
