/**
 * Input Validators
 */
const Joi = require('joi');

const signalSchema = Joi.object({
  frequency: Joi.number().required(),
  bandwidth_khz: Joi.number().optional(),
  snr_db: Joi.number().optional(),
  power_dbm: Joi.number().optional(),
  protocol_guess: Joi.string().optional(),
  protocol_confidence: Joi.number().min(0).max(1).optional(),
  decoder_used: Joi.string().optional(),
  decode_success: Joi.boolean().optional(),
  raw_metadata: Joi.object().optional(),
  sdr_device_serial: Joi.string().optional(),
});

const metadataSchema = Joi.object({
  radio_id: Joi.number().integer().required(),
  talkgroup: Joi.number().integer().optional(),
  time_slot: Joi.number().integer().valid(1, 2).optional(),
  call_type: Joi.string().valid('GROUP', 'PRIVATE', 'EMERGENCY', 'DATA', 'UNKNOWN').optional(),
  color_code: Joi.number().integer().optional(),
  protocol: Joi.string().optional(),
  frequency: Joi.number().optional(),
  encrypted: Joi.boolean().optional(),
  source_decoder: Joi.string().optional(),
});

const gpsSchema = Joi.object({
  radio_id: Joi.number().integer().required(),
  latitude: Joi.number().min(-90).max(90).required(),
  longitude: Joi.number().min(-180).max(180).required(),
  altitude: Joi.number().optional(),
  speed_kmh: Joi.number().optional(),
  heading: Joi.number().min(0).max(360).optional(),
  accuracy_m: Joi.number().optional(),
  source_protocol: Joi.string().optional(),
});

module.exports = { signalSchema, metadataSchema, gpsSchema };
