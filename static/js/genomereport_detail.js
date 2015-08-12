function guessGETEvidenceID (clinvarName) {
  var reFS = /\((.*?)\):.*?\(p\.(.*?[0-9]+)[A-Z][a-z][a-z]fs\)/
  var matchFS = reFS.exec(clinvarName)
  var reAASub = /\((.*?)\):.*?\(p\.([A-Za-z]+[0-9]+[A-Za-z]+)\)/
  var matchAASub = reAASub.exec(clinvarName)
  if (matchFS !== null) {
    return matchFS[1] + '-' + matchFS[2] + 'Shift'
  } else if (matchAASub !== null) {
    return matchAASub[1] + '-' + matchAASub[2].replace('Ter', 'Stop')
  }
  return ''
}

function addIdData (b37ID, clinvarRelationsData, template, elem) {
  var varNameString = ''
  var varNames = []
  clinvarRelationsData.forEach(function (clinvarData) {
    var prefName = clinvarData['clinvar-rcva:preferred-name']
    if (!prefName) return

    if (varNameString) {
      // If this name already listed, don't output again.
      if (_.contains(varNames, prefName)) return
      varNameString = varNameString + '</b><br><small>or</small><br><b>' +
                      prefName
    } else {
      varNameString = clinvarData['clinvar-rcva:preferred-name']
    }
    varNames.push(prefName)
  })
  // console.log(varNames)
  var getevID = guessGETEvidenceID(clinvarRelationsData[0]['clinvar-rcva:preferred-name'])
  var getevLink = 'http://evidence.pgp-hms.org/' + getevID
  var templated = template({
    clinvarRCVAPreferredName: varNameString,
    b37VariantID: b37ID,
    linkGETEvidence: getevLink
  })
  elem.append(templated)
  // console.log(elem)
  return [clinvarRelationsData[0]['clinvar-rcva:preferred-name'], b37ID, getevLink]
}

function addFreqData (b37ID, clinvarRelationsData, template, elem) {
  var frequencies = []
  clinvarRelationsData.forEach(function (clinvarData) {
    if ('clinvar-rcva:esp-allele-frequency' in clinvarData) {
      var freq = clinvarData['clinvar-rcva:esp-allele-frequency']
      if (_.contains(frequencies, freq)) return
      frequencies.push(freq)
    }
  })
  // console.log(frequencies)
  var frequency
  if (frequencies.length === 0) {
    frequency = 'Unknown'
  } else {
    frequency = frequencies[0]
  }
  linkExAC = 'http://exac.broadinstitute.org/variant/' + b37ID.substring(4)
  var templated = template({
    clinvarRCVAfreqESP: frequency,
    linkExAC: linkExAC
  })
  elem.append(templated)
  // console.log(elem)
  return [frequency, linkExAC]
}

function addInfoData (clinvarRelationsData, template, elem) {
  var returnData = []
  clinvarRelationsData.forEach(function (clinvarData) {
    var traitType = clinvarData['clinvar-rcva:trait-type']
    var traitLabel
    if (traitType === 'Disease') {
      traitLabel = 'Disease'
    } else {
      traitLabel = 'Trait'
    }
    var templated = template({
      clinvarTraitLabel: traitLabel,
      clinvarRCVAAccession: clinvarData['clinvar-rcva:accession'],
      clinvarRCVADiseaseName: clinvarData['clinvar-rcva:trait-name'],
      clinvarRCVASignificance: clinvarData['clinvar-rcva:significance']
    })
    // console.log(templated)
    elem.append(templated)
    returnData.push([
      traitLabel,
      clinvarData['clinvar-rcva:accession'],
      clinvarData['clinvar-rcva:trait-name'],
      clinvarData['clinvar-rcva:significance']
    ])
  })
  // console.log(elem)
  return returnData
}

function asCSVContent (idData, freqData, infoData) {
  var csvContent = ''
  infoData.forEach(function (infoDataItem) {
    var data = idData.concat(freqData).concat(infoDataItem).map(function (e) {
      return '"' + e + '"'
    })
    csvContent += data.join(',') + '\n'
  })
  return csvContent
}

function addGennotesData (data, textStatus, jqXHR) {
  // Build a CSV version of the data for download.
  var csvContent = ''

  data['results'].forEach(function (result) {
    // console.log(result['b37_id'])

    // Set up target elements by emptying them.
    var rowGV = $('tr#gv-' + result['b37_id'])
    var elemGVID = rowGV.find('td.gv-id-cell').empty()
    var elemGVFreq = rowGV.find('td.gv-freq-cell').empty()
    var elemGVInfo = rowGV.find('td.gv-info-cell').empty()

    // Load appropriate templates.
    var templateVariantID = _.template($('#variant-id-template').html())
    var templateVariantFreq = _.template($('#variant-freq-template').html())
    var templateVariantInfo = _.template($('#variant-info-template').html())

    // Extract list of Relations of type 'clinvar-rcva'.
    var clinvarRelationsData = []
    result['relation_set'].forEach(function (relation) {
      if (relation['tags']['type'] === 'clinvar-rcva') {
        clinvarRelationsData.push(relation['tags'])
      }
    })

    // No RCVA matches, prob variant was a multi-allele record - ignore it.
    if (clinvarRelationsData.length === 0) {
      rowGV.addClass('hidden')
      return
    }

    // console.log('Adding ClinVar data')
    var idData = addIdData(result['b37_id'], clinvarRelationsData, templateVariantID, elemGVID)
    var freqData = addFreqData(result['b37_id'], clinvarRelationsData, templateVariantFreq, elemGVFreq)
    var infoData = addInfoData(clinvarRelationsData, templateVariantInfo, elemGVInfo)

    csvContent += asCSVContent(idData, freqData, infoData)
  })

  // Add CSV download link.
  // console.log("Adding CSV data as link:")
  // console.log(csvContent)
  var downloadCSVDiv = $('div#download-as-csv').empty()
  var filenameCSV = $('#report-name').text() + '.csv'
  var downloadCSVLink = $('<a>Download as CSV file</a>')
    .attr('href', 'data:text/csv;charset=utf8,' + encodeURIComponent(csvContent))
    .attr('download', filenameCSV)
  downloadCSVDiv.append(downloadCSVLink)
}

$(function () {
  var variantList = $('tr.gv-row').map(function () {
    return $(this).attr('id').substring(3)
  }).toArray()
  // console.log(variantList)
  var variantListJSON = JSON.stringify(variantList)
  // console.log(variantListJSON)
  $.ajax({
    url: 'http://gennotes.herokuapp.com/api/variant/',
    dataType: 'json',
    data: {'variant_list': variantListJSON, 'page_size': 100},
    success: addGennotesData,
    error: function (jqXHR, err) {
      console.log('Error in AJAX call to GenNotes: ' + err)
    }
  })
})
