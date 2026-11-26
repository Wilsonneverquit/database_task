def describe_score(score):
    """Describe missing observations without fabricating activity or changing snapshots."""
    if score.get('total_score') is not None:
        status='scored';reason=''
    elif float(score.get('data_coverage') or 0)<.7:
        status='source_gap';reason='有效因子覆盖不足，需检查消费、出行或过车数据源的采集范围；当前不输出评分。'
    elif not score.get('sample_size') and float(score.get('data_coverage') or 0)<.9999:
        status='source_gap';reason='部分因子没有完整覆盖，且没有消费样本。需检查采集覆盖，不能直接认定为无活动。'
    elif not score.get('sample_size'):
        status='no_activity';reason='数据源覆盖完整，但近三小时没有消费记录，按样本门槛未评分。这是暂无消费活动，不是采集丢失，无需人为补造记录。'
    else:
        status='low_sample';reason='已有活动记录，但样本量未达到所属规则门槛，当前未评分。'
    label=({1:'低风险',2:'中风险',3:'高风险'}.get(score.get('risk_level'),'已评分') if status=='scored' else {'source_gap':'采集覆盖不足','no_activity':'暂无消费活动','low_sample':'样本不足'}[status])
    return score|dict(risk_status=status,status_reason=reason,status_label=label)
